"""
Crawls webshop URLs to find and identify product catalog pages
Stores product catalog URLs in MySQL database
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import time
from collections import deque, Counter
import urllib.robotparser
import random
import logging
import os
import sys
import re
import json
from pathlib import Path
from dotenv import load_dotenv
import warnings
from urllib3.exceptions import InsecureRequestWarning

warnings.filterwarnings('ignore', category=InsecureRequestWarning)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database.companies_db import CompaniesDB

load_dotenv()

CURRENT_FILE_DIR = Path(__file__).parent
AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent.parent
PROGRESS_FILE = AUTOMATION_ROOT / 'src' / 'products' / 'crawl' / 'progress.json'
LOG_DIR = AUTOMATION_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'product_crawler.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

MAX_SHOPS_TO_CRAWL = int(os.getenv('MAX_SHOPS_TO_CRAWL', 1689))
MAX_PAGES_PER_SHOP = int(os.getenv('MAX_PAGES_PER_SHOP', 30))
CRAWL_DELAY = int(os.getenv('CRAWL_DELAY', 1))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 12))

def load_last_index():
    """Load last processed shop index"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_index', 0)
    return 0

def save_last_index(index):
    """Save last processed shop index"""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'last_index': index}, f)

class ProductPageCrawler:
    def __init__(self, max_pages=30, delay=1, respect_robots=True):
        self.max_pages = max_pages
        self.delay = delay
        self.respect_robots = respect_robots

        self.visited = set()
        self.product_page_found = None
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })

        self.robots_cache = {}

        self.product_page_keywords = [
            'products', 'shop', 'catalog', 'catalogue', 'store', 'all-products',
            'produkte', 'sortiment', 'artikel', 'waren', 'kollektion', 'angebot',
            'collection', 'items', 'merchandise', 'goods', 'shopping',
            'category', 'categories', 'browse'
        ]

        self.product_url_patterns = [
            '/products', '/shop', '/catalog', '/catalogue', '/store',
            '/produkte', '/sortiment', '/artikel', '/kollektion',
            '/all-products', '/collections', '/items',
            '/category', '/categories', '/browse',
            '/men', '/women', '/kids', '/sale', '/new',
            '/clothing', '/shoes', '/accessories', '/c/'
        ]

        self.exclude_keywords = [
            'cart', 'checkout', 'account', 'login', 'register', 'wishlist',
            'warenkorb', 'kasse', 'konto', 'anmelden', 'wunschliste',
            'blog', 'news', 'about', 'contact', 'faq', 'help',
            'privacy', 'terms', 'impressum', 'datenschutz',
            'details', 'detail',
            'job', 'jobs', 'career', 'careers', 'recruit', 'recruiting',
            'play.google.com', 'apps/details',
            'storelocator', 'store-locator', 'find-store', 'locations',
            'trk.', 'track', 'redirect', 'click',
            '/oferta/', 'oferta'
        ]

        self.product_page_reached = False

    def normalize_url(self, url):
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        if not path:
            path = '/'
        
        normalized = urlunparse((
            parsed.scheme or 'http',
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            ''
        ))
        
        return normalized

    def domain_matches(self, url, base_domain):
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            base = base_domain.lower()
            return netloc == base or netloc.endswith('.' + base)
        except:
            return False

    def is_valid_url(self, url, base_domain):
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            return self.domain_matches(url, base_domain)
        except:
            return False

    def is_excluded_url(self, url):
        url_lower = url.lower()
        return any(kw in url_lower for kw in self.exclude_keywords)

    def is_product_url_pattern(self, url):
        url_lower = url.lower()
        
        if '/details' in url_lower or '/detail/' in url_lower:
            return False
        
        if any(kw in url_lower for kw in ['job', 'career', 'recruit', 'hiring']):
            return False
        
        if 'play.google.com' in url_lower:
            return False
        
        if '/apps/details' in url_lower or '/app/' in url_lower:
            return False
        
        return any(pattern in url_lower for pattern in self.product_url_patterns)

    def respects_robots(self, start_url, candidate_url):
        if not self.respect_robots:
            return True
        try:
            parsed = urlparse(start_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            ua = self.session.headers.get('User-Agent', '*')
            return rp.can_fetch(ua, candidate_url)
        except Exception:
            return True

    def detect_repeating_links(self, soup):
        links = [a.get('href', '') for a in soup.find_all('a', href=True)]
        
        patterns = []
        for link in links:
            pattern = re.sub(r'\d+', 'N', link)
            pattern = re.sub(r'[a-f0-9]{8,}', 'HASH', pattern)
            patterns.append(pattern)
        
        pattern_counts = Counter(patterns)
        max_repetition = max(pattern_counts.values()) if pattern_counts else 0
        
        return max_repetition

    def detect_ecommerce_platform(self, soup):
        html_lower = str(soup).lower()
        
        platforms = {
            'shopify': ['cdn.shopify.com', 'shopify-analytics'],
            'woocommerce': ['woocommerce', 'wc-'],
            'magento': ['magento', 'mage/cookies'],
            'prestashop': ['prestashop', 'ps_'],
            'bigcommerce': ['bigcommerce'],
            'opencart': ['opencart'],
        }
        
        for platform, signatures in platforms.items():
            if any(sig in html_lower for sig in signatures):
                return True
        
        return False

    def detect_product_elements(self, soup):
        product_indicators = 0
        
        product_card_classes = [
            'product-card', 'product-item', 'product-tile',
            'item-card', 'shop-item', 'catalog-item'
        ]
        
        product_cards = []
        for cls in product_card_classes:
            elements = soup.find_all(class_=lambda x: x and cls in x.lower())
            product_cards.extend(elements)
        
        if len(product_cards) >= 12:
            product_indicators += 3
        elif len(product_cards) >= 8:
            product_indicators += 2
        elif len(product_cards) >= 5:
            product_indicators += 1
        
        price_patterns = ['price', 'preis', 'cost', 'kosten']
        price_elements = []
        for pattern in price_patterns:
            price_elements.extend(soup.find_all(class_=lambda x: x and pattern in x.lower()))
            price_elements.extend(soup.find_all(attrs={'data-price': True}))
            price_elements.extend(soup.find_all(attrs={'itemprop': 'price'}))
        
        currency_symbols = soup.find_all(string=re.compile(r'[\$€£¥₹]'))
        price_elements.extend(currency_symbols)
        
        if len(price_elements) >= 12:
            product_indicators += 3
        elif len(price_elements) >= 8:
            product_indicators += 2
        elif len(price_elements) >= 5:
            product_indicators += 1
        
        cart_buttons = soup.find_all(['button', 'a'], string=lambda t: t and any(
            phrase in t.lower() for phrase in [
                'add to cart', 'in den warenkorb', 'add to bag', 'buy now',
                'kaufen', 'bestellen', 'add', 'hinzufügen', 'in den korb'
            ]
        ))
        
        cart_button_classes = soup.find_all(class_=lambda x: x and any(
            kw in x.lower() for kw in ['add-to-cart', 'add-cart', 'buy-button', 'kaufen', 'addtocart']
        ))
        
        total_cart_buttons = len(cart_buttons) + len(cart_button_classes)
        
        if total_cart_buttons >= 8:
            product_indicators += 3
        elif total_cart_buttons >= 5:
            product_indicators += 2
        elif total_cart_buttons >= 3:
            product_indicators += 1
        
        grid_containers = soup.find_all(class_=lambda x: x and any(
            kw in x.lower() for kw in [
                'product-grid', 'product-list', 'item-grid', 'catalog-grid',
                'product-listing', 'product-collection', 'category-products'
            ]
        ))
        
        if len(grid_containers) >= 2:
            product_indicators += 2
        elif len(grid_containers) >= 1:
            product_indicators += 1
        
        schema_products = soup.find_all(attrs={'itemtype': lambda x: x and 'product' in x.lower()})
        if len(schema_products) >= 5:
            product_indicators += 2
        elif len(schema_products) >= 3:
            product_indicators += 1
        
        pagination = soup.find_all(class_=lambda x: x and any(
            kw in x.lower() for kw in ['pagination', 'pager', 'page-numbers', 'paginate']
        ))
        if len(pagination) >= 1:
            product_indicators += 2
        
        filters = soup.find_all(class_=lambda x: x and any(
            kw in x.lower() for kw in ['filter', 'sort', 'refine', 'facet']
        ))
        if len(filters) >= 3:
            product_indicators += 2
        elif len(filters) >= 2:
            product_indicators += 1
        
        link_repetition = self.detect_repeating_links(soup)
        if link_repetition >= 15:
            product_indicators += 3
        elif link_repetition >= 10:
            product_indicators += 2
        elif link_repetition >= 6:
            product_indicators += 1
        
        if self.detect_ecommerce_platform(soup):
            product_indicators += 1
        
        return product_indicators

    def is_product_page(self, soup, url):
        if self.is_excluded_url(url):
            return False
        
        if not self.is_product_url_pattern(url):
            return False
        
        url_score = 3
        
        url_lower = url.lower()
        if any(kw in url_lower for kw in self.product_page_keywords):
            url_score += 1
        
        element_score = self.detect_product_elements(soup)
        
        total_score = url_score + element_score
        
        return total_score >= 6

    def find_product_links(self, soup, base_url):
        product_links = []
        for link in soup.find_all('a', href=True):
            url = self.normalize_url(urljoin(base_url, link['href']))
            link_text = link.get_text(strip=True).lower()
            
            if self.is_excluded_url(url):
                continue
            
            is_product_link = (
                self.is_product_url_pattern(url) or
                any(kw in link_text for kw in self.product_page_keywords) or
                any(kw in url.lower() for kw in self.product_page_keywords)
            )
            
            if is_product_link:
                product_links.append({
                    'url': url,
                    'text': link_text,
                    'priority': 10
                })
        
        return product_links

    def crawl_page(self, url, start_domain):
        normalized_url = self.normalize_url(url)
        if normalized_url in self.visited:
            return []

        if not self.respects_robots(start_domain, url):
            print(f"  ✗ Disallowed by robots.txt: {url}")
            self.visited.add(normalized_url)
            return []

        print(f"Crawling: {url}")
        self.visited.add(normalized_url)

        tries = 0
        max_tries = 2
        resp_text = None
        while tries <= max_tries:
            try:
                jitter = random.uniform(0, 0.3)
                time.sleep(jitter)
                response = self.session.get(url, timeout=REQUEST_TIMEOUT, verify=False)
                response.raise_for_status()
                resp_text = response.text
                break
            except Exception as e:
                tries += 1
                if tries > max_tries:
                    print(f"  ✗ Failed to fetch {url} after retries: {e}")
                    return []
                backoff = 1.5 ** tries
                print(f"  ✗ Request error ({tries}/{max_tries}) for {url}: {e} — retrying in {backoff:.1f}s")
                time.sleep(backoff)

        soup = BeautifulSoup(resp_text, 'html.parser')

        if self.is_product_page(soup, normalized_url):
            self.product_page_found = normalized_url
            self.product_page_reached = True
            print(f"  ★ Product catalog page detected: {normalized_url}")
            return []

        found_links = []
        base_domain = start_domain

        product_links = self.find_product_links(soup, url)
        if product_links:
            print(f"  → Found {len(product_links)} potential product page links")
            for pl in product_links:
                normalized_link = self.normalize_url(pl['url'])
                if normalized_link not in self.visited and normalized_link not in found_links:
                    found_links.append(normalized_link)

        all_links = soup.find_all('a', href=True)
        total_links_on_page = len(all_links)
        
        for link in all_links:
            href = link.get('href', '')
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
                
            absolute_url = urljoin(url, href)
            normalized_link = self.normalize_url(absolute_url)
            
            if normalized_link in self.visited:
                continue
            
            if normalized_link in found_links:
                continue
            
            if self.is_excluded_url(normalized_link):
                continue
            
            if self.is_valid_url(normalized_link, base_domain):
                found_links.append(normalized_link)

        if found_links:
            print(f"  → Extracted {len(found_links)} valid links (from {total_links_on_page} total links on page)")
        else:
            print(f"  ⚠ No valid links extracted (found {total_links_on_page} total links, all filtered out)")

        return found_links

    def crawl(self, start_url):
        parsed = urlparse(start_url)
        start_domain = parsed.netloc
        queue = deque([start_url])

        print(f"Starting product page crawl - will stop when product catalog is found\n")

        while queue and len(self.visited) < self.max_pages:
            url = queue.popleft()
            normalized_url = self.normalize_url(url)
            if normalized_url in self.visited:
                continue

            links = self.crawl_page(normalized_url, start_domain)

            if self.product_page_reached:
                print("Product catalog page found — halting further crawling for this shop.")
                break

            if not links:
                continue

            product_priority = []
            regular_links = []
            
            for link in links:
                if link in self.visited:
                    continue
                    
                if self.is_product_url_pattern(link):
                    product_priority.append(link)
                else:
                    regular_links.append(link)
            
            for link in product_priority:
                queue.appendleft(link)
            
            for link in regular_links:
                queue.append(link)

            time.sleep(self.delay)

        return self.product_page_found

if __name__ == "__main__":
    print("="*70)
    print("PRODUCT PAGE CRAWLER")
    print("="*70)
    print(f"Max shops: {MAX_SHOPS_TO_CRAWL} | Max pages per shop: {MAX_PAGES_PER_SHOP}")
    print(f"Delay: {CRAWL_DELAY}s | Timeout: {REQUEST_TIMEOUT}s")
    print("="*70 + "\n")

    db = CompaniesDB()

    urls_file = AUTOMATION_ROOT / 'src' / 'products' / 'urls' / 'urls.txt'
    
    if not urls_file.exists():
        print(f"✗ URLs file not found: {urls_file}")
        logger.error(f"URLs file not found: {urls_file}")
        exit(1)

    with open(urls_file, 'r', encoding='utf-8') as f:
        shop_urls = [line.strip() for line in f if line.strip()]

    if not shop_urls:
        print("✗ No shop URLs found in urls.txt")
        logger.error("No shop URLs found in urls.txt")
        exit(1)

    shop_urls = shop_urls[:MAX_SHOPS_TO_CRAWL]
    
    last_index = load_last_index()
    shops_to_process = shop_urls[last_index:]
    
    print(f"Total shops: {len(shop_urls)} | Starting from: {last_index + 1} | Remaining: {len(shops_to_process)}\n")

    product_pages_found = 0
    shops_processed = 0
    shops_failed = 0

    for i, shop_url in enumerate(shops_to_process):
        current_index = last_index + i
        
        if not shop_url.startswith('http'):
            shop_url = f'https://{shop_url}'

        print(f"[{current_index + 1}/{len(shop_urls)}] {shop_url}")

        crawler = ProductPageCrawler(
            max_pages=MAX_PAGES_PER_SHOP,
            delay=CRAWL_DELAY,
            respect_robots=True
        )

        try:
            product_page_url = crawler.crawl(shop_url)

            if product_page_url:
                success = db.save_product_page(shop_url, product_page_url)
                
                if success:
                    product_pages_found += 1
                    shops_processed += 1
                    print(f"  ✓ Saved: {product_page_url}\n")
                    logger.info(f"Saved product page: {product_page_url}")
                else:
                    shops_failed += 1
                    print(f"  ✗ Failed to save\n")
                    logger.error(f"Error saving product page for {shop_url}")
            else:
                shops_processed += 1
                print(f"  ⊘ No product page found\n")
                logger.warning(f"No product page found for {shop_url}")

        except Exception as e:
            shops_failed += 1
            print(f"  ✗ Error: {e}\n")
            logger.error(f"Error crawling {shop_url}: {e}")
        
        save_last_index(current_index + 1)

    print("="*70)
    print("FINAL SUMMARY")
    print("="*70)
    print(f"Processed: {shops_processed} | Found: {product_pages_found} | Failed: {shops_failed}")
    print(f"Success rate: {(product_pages_found/shops_processed*100) if shops_processed else 0:.1f}%")
    print("="*70 + "\n")

    try:
        stats = db.get_statistics()
        print(f"Total URLs in database: {stats.get('total_urls', 0)}")
        print(f"Product URLs: {stats.get('product_urls', 0)}\n")
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")

    print("✓ Crawling complete!")
    logger.info("Product page crawling completed successfully")
