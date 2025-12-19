"""
Company URL Finder - Database Version
Automated Google search to find company websites
Uses modular database structure with companies_db.py
"""

import os
import logging
import random
import time
import argparse
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv
import sys
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.companies_db import CompaniesDB
from utils.url_utils import detect_url_label

# Load environment variables
load_dotenv()

# Constants from .env
MAX_NAMES_TO_SEARCH = int(os.getenv('MAX_NAMES_TO_SEARCH', '1000'))
MAX_SUB_URLS = int(os.getenv('MAX_SUB_URLS', '5'))
MAX_ADDITIONAL_URLS = int(os.getenv('MAX_ADDITIONAL_URLS', '10'))
HEADLESS_MODE_DEFAULT = os.getenv('HEADLESS_MODE', 'false').lower() == 'true'

# Configure logging
CURRENT_FILE_DIR = Path(__file__).parent
AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent
LOG_DIR = AUTOMATION_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'company_url_finder.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Track performance metrics for batch processing"""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.company_timings = []
        
    def start_batch(self):
        self.start_time = datetime.now()
        logger.info(f"{'='*60}")
        logger.info(f"Batch processing started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'='*60}\n")
        
    def end_batch(self):
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Batch processing completed at: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Total duration: {duration}")
        
        if self.company_timings:
            avg_time = sum(self.company_timings) / len(self.company_timings)
            logger.info(f"Average time per company: {avg_time:.2f} seconds")
            logger.info(f"Fastest search: {min(self.company_timings):.2f} seconds")
            logger.info(f"Slowest search: {max(self.company_timings):.2f} seconds")
        
        logger.info(f"{'='*60}\n")
        
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'total_duration_seconds': duration.total_seconds(),
            'average_time_per_company': sum(self.company_timings) / len(self.company_timings) if self.company_timings else 0,
            'company_timings': self.company_timings
        }
    
    def track_company(self, company_name: str, duration: float):
        self.company_timings.append(duration)
        logger.info(f"  ⏱️  Search completed in {duration:.2f} seconds")

class SeleniumGoogleSearcher:
    """Handles Google search automation and URL extraction"""
    
    def __init__(self, headless: bool = None):
        """
        Initialize the Google searcher
        
        Args:
            headless: Run browser in headless mode (optional, reads from .env if not provided)
        """
        if headless is None:
            headless_env = os.getenv('HEADLESS_MODE', 'false').lower()
            headless = headless_env in ['true', '1', 'yes']
            logger.info(f"🔧 Headless mode from .env: {headless}")
        
        self.headless = headless
        self.chrome_options = self._setup_chrome_options()
        self.driver = None
        self.performance_tracker = PerformanceTracker()
        self.db = CompaniesDB()  # Use modular database class
        
    def _setup_chrome_options(self) -> Options:
        """Configure Chrome options for Selenium"""
        chrome_options = Options()
        
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        chrome_options.add_argument("--disable-images")
        chrome_options.page_load_strategy = 'eager'
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        return chrome_options
    
    def _create_driver(self):
        """Create and configure Chrome driver"""
        if self.driver is None:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(5)
            if not self.headless:
                self.driver.maximize_window()
        return self.driver
    
    def _close_driver(self):
        """Close Chrome driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _handle_cookie_consent(self):
        """Handle Google cookie consent dialog"""
        try:
            time.sleep(0.8)
            
            consent_selectors = [
                "//button[@id='L2AGLb']",
                "//button[contains(., 'Accept all')]",
                "//button[contains(., 'Alle akzeptieren')]",
                "//button[contains(@aria-label, 'Accept')]",
            ]
            
            for selector in consent_selectors:
                try:
                    consent_button = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    consent_button.click()
                    logger.debug("  ✓ Clicked cookie consent button")
                    time.sleep(0.5)
                    return True
                except (NoSuchElementException, TimeoutException):
                    continue
            
            logger.debug("  No cookie consent dialog found")
            return False
            
        except Exception as e:
            logger.debug(f"  Error handling cookie consent: {e}")
            return False
    
    def _get_base_domain(self, url: str) -> str:
        """Extract base domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same domain"""
        return self._get_base_domain(url1) == self._get_base_domain(url2)

    def google_search(self, company_name: str) -> Dict[str, any]:
        """
        Perform Google search and extract URLs
        
        Args:
            company_name: Name of company to search
            
        Returns:
            Dictionary with base_url, sub_urls, and additional_urls
        """
        search_start_time = time.time()
        
        try:
            driver = self._create_driver()
            
            logger.debug(f"  Navigating to Google...")
            driver.get("https://www.google.com")
            
            self._handle_cookie_consent()
            
            try:
                search_box = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.NAME, "q"))
                )
                search_box.clear()
                search_box.send_keys(company_name)
                search_box.send_keys(Keys.RETURN)
                logger.debug(f"  Search submitted")
            except TimeoutException:
                logger.error("  ✗ Could not find search box")
                return {"base_url": None, "sub_urls": [], "additional_urls": []}
            
            try:
                WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.ID, "search"))
                )
                time.sleep(1.0)
                logger.debug(f"  Results loaded")
            except TimeoutException:
                logger.error("  ✗ Search results did not load")
                return {"base_url": None, "sub_urls": [], "additional_urls": []}
            
            all_urls = []
            
            result_selectors = [
                "div.g a[href]",
                "#search a[href]",
                "div[data-sokoban-container] a[href]",
            ]
            
            for selector in result_selectors:
                try:
                    results = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for result in results[:30]:
                        try:
                            href = result.get_attribute("href")
                            
                            if not href or not href.startswith("http"):
                                continue
                            
                            if "google.com" in href:
                                continue
                            
                            if href not in all_urls:
                                all_urls.append(href)
                                logger.debug(f"  Found URL #{len(all_urls)}: {href}")
                            
                            if len(all_urls) >= 20:
                                break
                                
                        except Exception as e:
                            logger.debug(f"  Error processing result: {e}")
                            continue
                    
                    if len(all_urls) >= 20:
                        break
                    
                except Exception as e:
                    logger.debug(f"  Error with selector {selector}: {e}")
                    continue
            
            if all_urls:
                base_url = all_urls[0]
                base_domain = self._get_base_domain(base_url)
                
                sub_urls = []
                for url in all_urls[1:]:
                    if self._is_same_domain(url, base_url) and len(sub_urls) < MAX_SUB_URLS:
                        sub_urls.append(url)
                
                used_urls = {base_url} | set(sub_urls)
                additional_urls = [url for url in all_urls if url not in used_urls][:MAX_ADDITIONAL_URLS]
                
                search_duration = time.time() - search_start_time
                self.performance_tracker.track_company(company_name, search_duration)
                
                logger.debug(f"  Base URL: {base_url}")
                logger.debug(f"  Sub URLs: {len(sub_urls)}")
                logger.debug(f"  Additional URLs: {len(additional_urls)}")
                
                return {
                    "base_url": base_url,
                    "sub_urls": sub_urls,
                    "additional_urls": additional_urls
                }
            else:
                logger.debug("  ✗ No valid URLs found")
                search_duration = time.time() - search_start_time
                self.performance_tracker.track_company(company_name, search_duration)
                return {"base_url": None, "sub_urls": [], "additional_urls": []}
        
        except WebDriverException as e:
            logger.error(f"  ✗ WebDriver error: {e}")
            return {"base_url": None, "sub_urls": [], "additional_urls": []}
        except Exception as e:
            logger.error(f"  ✗ Unexpected error: {e}")
            return {"base_url": None, "sub_urls": [], "additional_urls": []}


    def process_companies(self, max_names: Optional[int] = None) -> Dict[str, int]:
        """
        Process companies from database
        
        Args:
            max_names: Maximum number of companies to process
            
        Returns:
            Dictionary with processing statistics
        """
        self.performance_tracker.start_batch()
        
        try:
            # Get pending companies from database using CompaniesDB
            companies = self.db.get_pending_companies(limit=max_names)
            
            if not companies:
                logger.info("No pending companies to process")
                perf_metrics = self.performance_tracker.end_batch()
                stats = self.db.get_statistics()
                return {
                    "processed": 0,
                    "found": stats.get('found', 0),
                    "not_found": stats.get('not_found', 0),
                    "performance": perf_metrics
                }
            
            logger.info(f"Processing {len(companies)} pending companies\n")
            
            found_count = 0
            not_found_count = 0
            error_count = 0
            
            for i, (company_id, company_name) in enumerate(companies, 1):
                logger.info(f"[{i}/{len(companies)}] Searching for: {company_name}")
                
                try:
                    result = self.google_search(company_name)
                    
                    if result['base_url']:
                        logger.info(f"  ✓ Base URL: {result['base_url']}")
                        
                        # Update base_url in companies table
                        self.db.update_company_status(company_id, result['base_url'], 'found')
                        
                        # Insert sub-URLs with labels
                        if result['sub_urls']:
                            logger.info(f"  ✓ Sub URLs found: {len(result['sub_urls'])}")
                            for idx, url in enumerate(result['sub_urls'], 1):
                                label = detect_url_label(url)
                                logger.info(f"    {idx}. [{label}] {url}")
                            self.db.insert_sub_urls(company_id, result['sub_urls'])
                        
                        # Insert additional URLs
                        if result['additional_urls']:
                            logger.info(f"  ✓ Additional URLs found: {len(result['additional_urls'])}")
                            for idx, url in enumerate(result['additional_urls'], 1):
                                logger.info(f"    {idx}. {url}")
                            self.db.insert_additional_urls(company_id, result['additional_urls'])
                        
                        found_count += 1
                    else:
                        logger.info(f"  ✗ No website found")
                        self.db.update_company_status(company_id, None, 'not_found')
                        not_found_count += 1
                    
                    # Delay between searches
                    if i < len(companies):
                        time.sleep(1.5)
                
                except Exception as e:
                    logger.error(f"  ✗ Error processing company '{company_name}': {e}")
                    self.db.update_company_status(company_id, None, 'error')
                    error_count += 1
            
            perf_metrics = self.performance_tracker.end_batch()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✓ Processing complete!")
            logger.info(f"Summary: Found {found_count}, Not found {not_found_count}, Errors {error_count}")
            logger.info(f"{'='*60}\n")
            
            return {
                "processed": len(companies),
                "found": found_count,
                "not_found": not_found_count,
                "error": error_count,
                "performance": perf_metrics
            }
        
        finally:
            self._close_driver()


def main():
    """Main execution function with configurable batch size"""
    
    parser = argparse.ArgumentParser(description='Company URL Finder - Scrape company websites')
    parser.add_argument('-b', '--batch', type=int, default=None, 
                       help='Number of companies to process (default: interactive menu)')
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode')
    args = parser.parse_args()
    
    print("\n" + "=" * 70)
    print("  COMPANY URL FINDER - DATABASE VERSION")
    print("=" * 70 + "\n")
    
    batch_size = args.batch
    
    if batch_size is None:
        print("How many companies would you like to process?")
        print("  1. Process 10 companies (Quick test)")
        print("  2. Process 50 companies (Small batch)")
        print("  3. Process 100 companies (Medium batch)")
        print("  4. Process 200 companies (Large batch)")
        print("  5. Process ALL pending companies")
        print("  6. Custom number")
        print()
        
        choice = input("Enter your choice (1-6): ").strip()
        
        if choice == '1':
            batch_size = 10
        elif choice == '2':
            batch_size = 50
        elif choice == '3':
            batch_size = 100
        elif choice == '4':
            batch_size = 200
        elif choice == '5':
            batch_size = None
        elif choice == '6':
            try:
                batch_size = int(input("Enter number of companies: ").strip())
                if batch_size <= 0:
                    print("Invalid number. Processing all pending companies.")
                    batch_size = None
            except ValueError:
                print("Invalid number. Processing all pending companies.")
                batch_size = None
        else:
            print("Invalid choice. Processing all pending companies.")
            batch_size = None
    
    if batch_size:
        print(f"\n📊 Batch size set to: {batch_size} companies\n")
    else:
        print(f"\n📊 Processing ALL pending companies\n")
    
    if args.headless:
        headless_mode = True
        print("🔧 Headless mode: Enabled (from command-line)")
    else:
        headless_env = os.getenv('HEADLESS_MODE', 'false').lower()
        headless_mode = headless_env in ['true', '1', 'yes']
        print(f"🔧 Headless mode: {'Enabled' if headless_mode else 'Disabled'} (from .env)")
    
    searcher = SeleniumGoogleSearcher(headless=headless_mode)
    
    try:
        stats = searcher.db.get_statistics()
        print(f"\nDatabase Statistics:")
        print(f"  Total companies: {stats.get('total_companies', 0)}")
        print(f"  Pending: {stats.get('pending', 0)}")
        print(f"  Found: {stats.get('found', 0)}")
        print(f"  Not found: {stats.get('not_found', 0)}")
        print(f"  Errors: {stats.get('error', 0)}")
        print(f"  Total URLs: {stats.get('total_urls', 0)}")
        print(f"    └─ Base URLs: {stats.get('base_urls', 0)}")
        print(f"    └─ Sub URLs: {stats.get('sub_urls', 0)}")
        print(f"    └─ Additional URLs: {stats.get('additional_urls', 0)}")
        print()
        
        result = searcher.process_companies(max_names=batch_size)
        
        print(f"\n{'='*70}")
        print(f"Processing complete!")
        print(f"Processed: {result['processed']}")
        print(f"Found: {result['found']}")
        print(f"Not found: {result['not_found']}")
        print(f"Errors: {result.get('error', 0)}")
        
        if 'performance' in result:
            perf = result['performance']
            print(f"\nPerformance Metrics:")
            print(f"Total Duration: {perf['total_duration_seconds']:.2f} seconds")
            print(f"Average per Company: {perf['average_time_per_company']:.2f} seconds")
        
        final_stats = searcher.db.get_statistics()
        print(f"\nFinal Database Statistics:")
        print(f"  Pending: {final_stats.get('pending', 0)}")
        print(f"  Found: {final_stats.get('found', 0)}")
        print(f"  Not found: {final_stats.get('not_found', 0)}")
        print(f"  Total URLs: {final_stats.get('total_urls', 0)}")
        print(f"    └─ Base URLs: {final_stats.get('base_urls', 0)}")
        print(f"    └─ Sub URLs: {final_stats.get('sub_urls', 0)}")
        print(f"    └─ Additional URLs: {final_stats.get('additional_urls', 0)}")
        
        print(f"{'='*70}")
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"\nAn error occurred: {e}")
    
    finally:
        pass


if __name__ == "__main__":
    main()
