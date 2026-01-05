"""
Crawls company websites to find and extract contact forms
Stores results in MySQL database instead of JSON files
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import time
from collections import deque
import urllib.robotparser
import random
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.contact_forms_db import ContactFormsDB
from database.companies_db import CompaniesDB  

# Load environment variables
load_dotenv()

# Setup logging
CURRENT_FILE_DIR = Path(__file__).parent
AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent
LOG_DIR = AUTOMATION_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'contact_scraper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION FROM .ENV ============
MAX_COMPANIES_TO_CRAWL = int(os.getenv('MAX_COMPANIES_TO_CRAWL', 800))
MAX_PAGES_PER_COMPANY = int(os.getenv('MAX_PAGES_PER_COMPANY', 20))
CRAWL_DELAY = int(os.getenv('CRAWL_DELAY', 1))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', 12))
# ================================================


class ContactFormCrawler:
    def __init__(self, max_pages=50, delay=1, prioritize_contact=True, respect_robots=True):
        self.max_pages = max_pages
        self.delay = delay
        self.prioritize_contact = prioritize_contact
        self.respect_robots = respect_robots

        self.visited = set()
        self.forms_found = []
        self.contact_pages = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9,de;q=0.8'
        })

        self.contact_page_keywords = [
            'contact', 'get-in-touch', 'reach-us', 'contactus', 'contact-us', 'touch',
            'reach', 'get_in_touch', 'support', 'help', 'feedback', 'inquiry', 'enquiry',
            'customer-service', 'helpdesk', 'kontakt',
            'kontakt', 'kontaktformular', 'kontaktieren', 'anfrage', 'anfragen', 'nachricht',
            'formular', 'hilfe', 'unterstützung', 'kundenservice', 'kontaktieren-sie-uns'
        ]

        self.newsletter_keywords = ['newsletter', 'subscribe', 'subscription', 'signup', 'anmeldung', 'abonnieren']
        self.auth_keywords = ['login', 'register', 'signin', 'signup', 'password', 'anmelden', 'registrieren', 'passwort']
        self.product_keywords = ['product name', 'product url', 'product_name', 'product_url', 'variant', 'sku', 'cart', 'add-to-cart']
        self.salutation_keywords = [
            'salutation', 'title', 'anrede', 'herr', 'frau', 'mx', 'mr', 'mrs', 'miss', 'dr', 'prof', 'divers', 'keine angabe'
        ]

        self.contact_page_reached = False
        
        self.sub_urls_to_check = []
        self.companies_db = None
    
    
    def normalize_url(self, url):
        """
        Normalize URL: remove fragments, trailing slashes, and duplicate path segments
        """
        parsed = urlparse(url)
        
        segments = [s for s in parsed.path.split('/') if s]
        
        temp_segments = []
        prev = None
        for seg in segments:
            if seg != prev:
                temp_segments.append(seg)
            prev = seg
        
        seen_positions = {}
        for i, seg in enumerate(temp_segments):
            seen_positions[seg] = i
        
        final_segments = []
        for i, seg in enumerate(temp_segments):
            if seen_positions[seg] == i:
                final_segments.append(seg)
        
        if len(final_segments) >= 2:
            first_seg = final_segments[0]
            if first_seg in ['schmutzer', 'schmutzer_module', 'shop']:
                rest_of_path = final_segments[1:]
                if rest_of_path and rest_of_path[0] in ['schmutzer', 'schmutzer_module', 'shop']:
                    final_segments = rest_of_path
        
        if final_segments:
            normalized_path = '/' + '/'.join(final_segments)
        else:
            normalized_path = '/'
        
        normalized = urlunparse((
            parsed.scheme or 'http',
            parsed.netloc.lower(),
            normalized_path,
            parsed.params,
            parsed.query,
            ''
        ))
        
        return normalized

    def domain_matches(self, url, base_domain):
        """Return true if url belongs to base_domain (allow subdomains)"""
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            base = base_domain.lower()
            return netloc == base or netloc.endswith('.' + base)
        except:
            return False

    def is_valid_url(self, url, base_domain):
        """Check if URL is a valid http(s) URL and belongs to same domain"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https'):
                return False
            return self.domain_matches(url, base_domain)
        except:
            return False

    def is_contact_page(self, url, link_text=''):
        """Check if URL or link text suggests it's a contact page"""
        url_lower = (url or '').lower()
        text_lower = (link_text or '').lower()
        return any(kw in url_lower or kw in text_lower for kw in self.contact_page_keywords)

    def is_strict_contact_url(self, url):
        """Stricter contact URL recognition for Option B"""
        if not url:
            return False
        u = url.lower()
        strict_patterns = [
            '/contact', '/contact/', '/contact-us', '/contact-us/', '/kontakt', '/kontakt/',
            '/kontaktformular', '/kontaktformular/', '/kontakt/kontakt', '/support/contact',
            '/customer-service/contact', 'contact.html', 'kontakt.html', '/kontakt/contact'
        ]
        for p in strict_patterns:
            if u.endswith(p) or p in u:
                return True
        if any(u.endswith(name) for name in ['contact.php', 'contact.html', 'kontakt.php', 'kontakt.html']):
            return True
        return False
    
    def find_contact_links(self, soup, base_url):
        """Find links that likely point to contact pages"""
        contact_links = []
        for link in soup.find_all('a', href=True):
            url = self.normalize_url(urljoin(base_url, link['href']))  
            link_text = link.get_text(strip=True)
            if self.is_contact_page(url, link_text) or self.is_strict_contact_url(url):
                contact_links.append({
                    'url': url,
                    'text': link_text,
                    'priority': 10
                })
        return contact_links

    def respects_robots(self, start_url, candidate_url):
        """Check robots.txt for the candidate domain if enabled"""
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

    def detect_field_role(self, field, form):
        """Heuristic to detect the role of an input field"""
        attrs_text = ' '.join([
            (field.get('name') or ''),
            (field.get('id') or ''),
            (field.get('placeholder') or ''),
            (field.get('type') or ''),
            (field.get('aria-label') or ''),
            (field.get('title') or '')
        ]).lower()

        label_text = ''
        fid = field.get('id')
        if fid:
            label = form.find('label', {'for': fid})
            if label:
                label_text = label.get_text(strip=True).lower()

        combined = f"{attrs_text} {label_text}"

        if 'email' in combined or 'e-mail' in combined or 'e_mail' in combined or 'mail' in combined:
            return 'email'
        if 'message' in combined or 'nachricht' in combined or field.name == 'textarea' or 'message' in label_text:
            return 'message'
        if any(k in combined for k in ['name', 'vorname', 'nachname', 'full_name', 'fullname', 'givenname', 'surname']):
            return 'name'
        if 'phone' in combined or 'tel' in combined or 'telefon' in combined or 'mobile' in combined or 'handy' in combined:
            return 'phone'
        if any(k in combined for k in ['address', 'adresse', 'street', 'straße', 'plz', 'postal', 'city', 'ort']):
            return 'address'
        if any(k in combined for k in self.salutation_keywords):
            return 'salutation'

        return 'unknown'

    def is_contact_form(self, form, page_url=''):
        """Heuristics to identify if a form is likely a contact form"""
        action = (form.get('action') or '').lower()
        form_id = (form.get('id') or '').lower()
        form_class = ' '.join(form.get('class', [])).lower()

        if any(kw in action or kw in form_id or kw in form_class for kw in self.newsletter_keywords):
            return False
        if any(kw in action or kw in form_id or kw in form_class for kw in self.auth_keywords):
            return False

        inputs = form.find_all(['input', 'textarea', 'select'])
        visible_inputs = [inp for inp in inputs if inp.get('type', '').lower() not in ['hidden', 'submit', 'button', 'checkbox', 'radio']]

        if len(visible_inputs) < 1:
            return False

        hidden_names = [inp.get('name', '').lower() for inp in inputs if inp.get('type','').lower() == 'hidden']
        if any(any(pk in hn for pk in self.product_keywords) for hn in hidden_names):
            return False

        roles = [self.detect_field_role(inp, form) for inp in inputs]
        has_email = 'email' in roles
        has_message = 'message' in roles
        has_name = 'name' in roles
        has_salutation = 'salutation' in roles

        is_on_strict_contact_url = self.is_strict_contact_url(page_url) or any(self.is_strict_contact_url(a.get('href','') or '') for a in form.find_all('a', href=True))

        if is_on_strict_contact_url:
            if any([has_email, has_name, has_message, has_salutation]):
                return True
            return False

        contact_attr_keywords = ['contact', 'inquiry', 'enquiry', 'reach', 'feedback', 'get-in-touch', 'kontakt', 'anfrage', 'nachricht', 'kontaktformular', 'kontaktaufnahme']
        has_contact_attr = any(kw in action or kw in form_id or kw in form_class for kw in contact_attr_keywords)
        is_on_contact_page = any(kw in page_url.lower() for kw in self.contact_page_keywords)

        sufficient_structure = (has_email and (has_message or has_name)) or (has_name and has_message) or has_contact_attr or is_on_contact_page

        if not is_on_strict_contact_url and len(visible_inputs) < 2:
            return False

        return sufficient_structure


    def extract_submit_buttons(self, form):
        """Extract all submit buttons with comprehensive attribute checking"""
        buttons = []

        for submit in form.find_all('input', {'type': 'submit'}):
            button_info = {
                'element': 'input',
                'type': 'submit',
                'name': submit.get('name', ''),
                'id': submit.get('id', ''),
                'value': submit.get('value', ''),
                'class': ' '.join(submit.get('class', [])),
                'text': submit.get('value', ''),
                'aria_label': submit.get('aria-label', ''),
                'data_hook': submit.get('data-hook', ''),
                'onclick': submit.get('onclick', ''),
                'formaction': submit.get('formaction', '')
            }
            buttons.append(button_info)

        for button in form.find_all('button'):
            button_type = button.get('type', '').lower()
            button_class = ' '.join(button.get('class', [])).lower()
            button_id = (button.get('id') or '').lower()
            button_name = (button.get('name') or '').lower()
            button_data_hook = (button.get('data-hook') or '').lower()

            is_submit = False

            if button_type in ['submit', '']:
                is_submit = True
            elif button_type == 'button':
                submit_indicators = [
                    'submit' in button_class,
                    'submit' in button_id,
                    'submit' in button_name,
                    'submit' in button_data_hook,
                    'send' in button_class or 'send' in button_id or 'senden' in button_class or 'senden' in button_id,
                    button.get('onclick', '').lower().find('submit') != -1,
                    (button.get('formaction') or '') != ''
                ]
                is_submit = any(submit_indicators)

            if is_submit:
                button_info = {
                    'element': 'button',
                    'type': button_type or 'submit',
                    'name': button.get('name', ''),
                    'id': button.get('id', ''),
                    'value': button.get('value', ''),
                    'class': ' '.join(button.get('class', [])),
                    'text': button.get_text(strip=True),
                    'aria_label': button.get('aria-label', ''),
                    'data_hook': button.get('data-hook', ''),
                    'data_action': button.get('data-action', ''),
                    'data_type': button.get('data-type', ''),
                    'onclick': button.get('onclick', ''),
                    'formaction': button.get('formaction', ''),
                    'role': button.get('role', '')
                }
                buttons.append(button_info)

        for elem in form.find_all(attrs={'role': 'button'}):
            if elem.name not in ['input', 'button']:
                elem_attrs = ' '.join([
                    ' '.join(elem.get('class', [])) if isinstance(elem.get('class', []), list) else (elem.get('class') or ''),
                    elem.get('id', '') or '',
                    elem.get('data-hook', '') or '',
                    elem.get('onclick', '') or ''
                ]).lower()
                if 'submit' in elem_attrs or 'send' in elem_attrs or 'senden' in elem_attrs:
                    button_info = {
                        'element': elem.name,
                        'type': 'role-button',
                        'name': elem.get('name', ''),
                        'id': elem.get('id', ''),
                        'value': elem.get('value', ''),
                        'class': ' '.join(elem.get('class', [])) if isinstance(elem.get('class', []), list) else elem.get('class', ''),
                        'text': elem.get_text(strip=True),
                        'aria_label': elem.get('aria-label', ''),
                        'data_hook': elem.get('data-hook', ''),
                        'data_action': elem.get('data-action', ''),
                        'onclick': elem.get('onclick', ''),
                        'role': 'button'
                    }
                    buttons.append(button_info)

        return buttons
    
    def extract_form_data(self, form, page_url):
        """Extract form fields and endpoint info with roles and options"""
        form_data = {
            'page_url': page_url,
            'action': form.get('action', '') or '',
            'method': (form.get('method') or 'get').upper(),
            'fields': [],
            'submit_buttons': []
        }

        if form_data['action']:
            form_data['action'] = self.normalize_url(urljoin(page_url, form_data['action']))
        else:
            form_data['action'] = page_url

        for idx, field in enumerate(form.find_all(['input', 'textarea', 'select'])):
            ftype = (field.get('type') or field.name).lower()
            name = field.get('name') or ''
            fid = field.get('id') or ''
            placeholder = field.get('placeholder') or ''
            required = field.has_attr('required')
            value = field.get('value') or ''

            label_text = ''
            if fid:
                lab = form.find('label', {'for': fid})
                if lab:
                    label_text = lab.get_text(strip=True)
            if not label_text:
                parent_label = field.find_parent('label')
                if parent_label:
                    label_text = parent_label.get_text(strip=True)

            if not label_text:
                label_text = field.get('aria-label') or field.get('title') or ''

            field_info = {
                'type': ftype,
                'name': name,
                'id': fid,
                'placeholder': placeholder,
                'label': label_text,
                'required': required,
                'value': value,
                'role': self.detect_field_role(field, form)
            }

            if field.name == 'select':
                options = []
                for opt in field.find_all('option'):
                    opt_val = (opt.get('value') or '').strip()
                    opt_label = (opt.get_text(strip=True) or '').strip()

                    placeholder_texts = {'', 'select', 'please select', 'please choose', 'bitte wählen', '-- select --', '-- wählen --', 'choose', 'auswählen'}
                    if opt_label.lower() in placeholder_texts:
                        continue

                    if not opt_val:
                        opt_val = opt_label

                    options.append({'value': opt_val, 'label': opt_label})

                field_info['options'] = options

                salutation_set = {'herr', 'frau', 'mr', 'mrs', 'ms', 'mx', 'dr', 'prof', 'divers', 'keine angabe'}
                if any(o['label'].strip().lower() in salutation_set for o in options):
                    field_info['role'] = 'salutation'

            if not field_info['name'] and not field_info['id']:
                field_info['generated_name'] = f'unnamed_field_{idx}'

            form_data['fields'].append(field_info)

        form_data['submit_buttons'] = self.extract_submit_buttons(form)
        return form_data

    def _is_real_contact_form(self, form_info):
        """Return True only if form_info looks like a likely contact form"""
        fields = form_info.get("fields", [])

        names = [(f.get("name") or "").lower() for f in fields]
        types = [(f.get("type") or "").lower() for f in fields]
        placeholders = [(f.get("placeholder") or "").lower() for f in fields]
        labels = [(f.get("label") or "").lower() for f in fields]

        text = " ".join(names + placeholders + labels)

        bad_keywords = [
            "passwort", "password", "login", "anmelden", "konto", "mein-konto",
            "warenkorb", "cart", "schnellkauf", "ean", "quick", "schnellkauf"
        ]
        if any(bad in text for bad in bad_keywords):
            return False

        unique_types = set([t for t in types if t])
        if unique_types <= {"email", "password", "hidden"} and "password" in unique_types:
            return False

        good_keywords = ["nachricht", "message", "vorname", "nachname", "betreff", "subject", "kontakt"]
        if any(good in text for good in good_keywords):
            return True

        submit_texts = [(btn.get("text") or "").lower() for btn in form_info.get("submit_buttons", [])]
        contact_words = ["send", "senden", "abschicken", "nachricht", "kontakt", "submit", "abschicken"]
        if any(any(word in s for word in contact_words) for s in submit_texts if s):
            return True

        for f in fields:
            if f.get("role") == "salutation":
                return True

        return False

    def crawl_page(self, url, start_domain):
        """Crawl one page, extract contact forms and candidate links"""
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
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
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
        found_links = []

        strict_contact = self.is_strict_contact_url(normalized_url) or self.is_contact_page(normalized_url)
        if strict_contact:
            self.contact_pages.append(normalized_url)
            self.contact_page_reached = True
            print(f"  ★ Strict contact page detected: {normalized_url}")

        raw_forms = soup.find_all('form')
        contact_forms_count = 0
        
        for form in raw_forms:
            try:
                if not self.is_contact_form(form, normalized_url):
                    continue

                form_data = self.extract_form_data(form, normalized_url)

                if not self._is_real_contact_form(form_data):
                    continue

                is_duplicate = any(
                    (existing['action'] == form_data['action'] and existing['page_url'] == form_data['page_url'])
                    for existing in self.forms_found
                )
                if not is_duplicate:
                    form_data['html_content'] = resp_text
                    self.forms_found.append(form_data)
                    contact_forms_count += 1
                    print(f"  ✓ Found contact form with {len(form_data['fields'])} fields and {len(form_data['submit_buttons'])} submit button(s)")
                else:
                    print(f"  ⊘ Skipped duplicate form (action/page match)")
            except Exception as e:
                print(f"  ✗ Error analyzing form: {e}")

        if normalized_url in self.sub_urls_to_check:
            has_form = contact_forms_count > 0
            if self.companies_db:
                try:
                    self.companies_db.update_sub_url_form(normalized_url, has_form)
                    logger.debug(f"Updated sub_url form status: {normalized_url} -> {has_form}")
                except Exception as e:
                    logger.error(f"Error updating sub_url form status for {normalized_url}: {e}")

        if strict_contact:
            print("  → Option B active: not following other links because contact PAGE reached.")
            return []

        contact_links = self.find_contact_links(soup, url)
        if contact_links:
            print(f"  → Found {len(contact_links)} potential contact page links")
            for cl in contact_links:
                normalized_link = self.normalize_url(cl['url'])
                if normalized_link not in self.visited:
                    found_links.insert(0, normalized_link)

        base_domain = start_domain
        for link in soup.find_all('a', href=True):
            absolute_url = urljoin(url, link['href'])
            normalized_link = self.normalize_url(absolute_url)
            if self.is_valid_url(normalized_link, base_domain):
                if normalized_link not in [self.normalize_url(l) for l in found_links]:
                    found_links.append(normalized_link)

        return found_links
    
    def crawl(self, start_url, company_id=None):
        """Main BFS crawl; Option B: if a contact PAGE is reached, we stop following other pages"""
        parsed = urlparse(start_url)
        start_domain = parsed.netloc
        queue = deque([start_url])

        if company_id and self.companies_db:
            try:
                sub_urls_data = self.companies_db.get_sub_urls(company_id)
                self.sub_urls_to_check = [self.normalize_url(s['url']) for s in sub_urls_data]
                
                for sub_url in self.sub_urls_to_check:
                    normalized_sub = self.normalize_url(sub_url)
                    if normalized_sub not in self.visited:
                        queue.appendleft(normalized_sub)
                
                if self.sub_urls_to_check:
                    logger.info(f"Added {len(self.sub_urls_to_check)} sub_urls to crawl queue")
            except Exception as e:
                logger.error(f"Error fetching sub_urls for company_id {company_id}: {e}")

        print(f"Starting intelligent crawl - will prioritize contact pages (Option B: stop on contact PAGE)\n")

        while queue and len(self.visited) < self.max_pages:
            url = queue.popleft()
            normalized_url = self.normalize_url(url)
            if normalized_url in self.visited:
                continue

            links = self.crawl_page(normalized_url, start_domain)

            if self.contact_page_reached:
                print("Contact page was reached — halting further page traversal for this company.")
                break

            if self.prioritize_contact:
                contact_first = []
                other_links = []
                for link in links:
                    normalized_link = self.normalize_url(link)
                    
                    if self.is_contact_page(normalized_link) and normalized_link not in self.visited:
                        contact_first.append(normalized_link)
                    elif normalized_link not in self.visited:
                        other_links.append(normalized_link)
                        
                queue.extendleft(reversed(contact_first))
                queue.extend(other_links)
            else:
                for link in links:
                    normalized_link = self.normalize_url(link)
                    if normalized_link not in self.visited:
                        queue.append(normalized_link)

            time.sleep(self.delay)

            if len(self.visited) >= self.max_pages:
                break

        return self.forms_found


# ============ MAIN SCRIPT ============
if __name__ == "__main__":
    print("="*70)
    print("CONTACT FORM CRAWLER - DATABASE VERSION")
    print("="*70)
    print(f"Configuration:")
    print(f"  - Max companies to crawl: {MAX_COMPANIES_TO_CRAWL}")
    print(f"  - Max pages per company: {MAX_PAGES_PER_COMPANY}")
    print(f"  - Delay between requests: {CRAWL_DELAY}s")
    print("="*70 + "\n")

    db = ContactFormsDB()
    companies_db = CompaniesDB()

    companies = db.get_companies_to_scrape(limit=MAX_COMPANIES_TO_CRAWL, only_unscraped=True)

    if not companies:
        print("No companies found to crawl. Exiting.")
        logger.info("No unscraped companies found in database")
        exit(1)

    print(f"Loaded {len(companies)} companies from database")
    print(f"Processing {len(companies)} companies\n")

    all_forms_count = 0

    for i, company_data in enumerate(companies, 1):
        company_id = company_data['company_id']
        company_name = company_data['company_name']
        company_url = company_data['url']

        if not company_url:
            print(f"[{i}/{len(companies)}] Skipping {company_name} - no URL\n")
            continue

        print(f"\n{'='*70}")
        print(f"[{i}/{len(companies)}] Processing: {company_name}")
        print(f"URL: {company_url}")
        print('='*70)

        crawler = ContactFormCrawler(
            max_pages=MAX_PAGES_PER_COMPANY,
            delay=CRAWL_DELAY,
            prioritize_contact=True,
            respect_robots=True
        )
        
        crawler.companies_db = companies_db

        forms = crawler.crawl(company_url, company_id=company_id)

        for form in forms:
            try:
                form_data = {
                    'action': form['action'],
                    'fields': form['fields'],
                    'submit_buttons': form['submit_buttons']
                }

                success = db.insert_contact_form(
                    company_id=company_id,
                    page_url=form['page_url'],
                    method=form['method'],
                    form_data=form_data,
                    html_content=form.get('html_content')
                )

                if success:
                    all_forms_count += 1
                    logger.info(f"Saved form for {company_name} from {form['page_url']}")
                else:
                    logger.error(f"Failed to save form for {company_name}")

            except Exception as e:
                logger.error(f"Error saving form for {company_name}: {e}")

        db.mark_company_scraped(company_id)

        print(f"\n  Summary for {company_name}:")
        print(f"    - Forms found: {len(forms)}")
        print(f"    - Pages visited: {len(crawler.visited)}")
        print(f"    - Contact pages found: {len(crawler.contact_pages)}")

    print(f"\n\n{'='*70}")
    print("FINAL SUMMARY")
    print('='*70)
    print(f"Total companies processed: {len(companies)}")
    print(f"Total contact forms saved to database: {all_forms_count}")
    print('='*70 + "\n")

    stats = db.get_statistics()
    print("Database Statistics:")
    print(f"  - Total companies to scrape: {stats.get('total_companies', 0)}")
    print(f"  - Scraped: {stats.get('scraped', 0)}")
    print(f"  - Pending: {stats.get('pending', 0)}")
    print(f"  - Total forms in database: {stats.get('total_forms', 0)}")
    print(f"  - Companies with forms: {stats.get('companies_with_forms', 0)}")

    print("\n✓ Crawling complete!")
    logger.info("Contact form scraping completed successfully")
