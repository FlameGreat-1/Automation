import os
import json
import logging
import random
import time
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, WebDriverException, TimeoutException


MAX_NAMES_TO_SEARCH = 1000
MAX_SUB_URLS = 5
MAX_ADDITIONAL_URLS = 10


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTracker:
    
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
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.chrome_options = self._setup_chrome_options()
        self.driver = None
        self.performance_tracker = PerformanceTracker()
        
    def _setup_chrome_options(self) -> Options:
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
        ##chrome_options.add_argument("--disable-javascript")
        chrome_options.page_load_strategy = 'eager'
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        return chrome_options
    
    def _create_driver(self):
        if self.driver is None:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.driver.implicitly_wait(5)
            if not self.headless:
                self.driver.maximize_window()
        return self.driver
    
    def _close_driver(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def _handle_cookie_consent(self):
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
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return ""
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        return self._get_base_domain(url1) == self._get_base_domain(url2)

    def google_search(self, company_name: str) -> Dict[str, any]:
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

    def process_companies(self,
                         input_file: str = "company_names.json",
                         output_file: str = "company_urls.json",
                         max_names: Optional[int] = None) -> Dict[str, int]:
        
        self.performance_tracker.start_batch()
        
        try:
            try:
                with open(input_file, 'r', encoding='utf-8') as f:
                    companies = json.load(f)
            except FileNotFoundError:
                logger.error(f"Input file '{input_file}' not found")
                return {"processed": 0, "found": 0, "not_found": 0}
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in '{input_file}'")
                return {"processed": 0, "found": 0, "not_found": 0}
            
            if max_names is not None:
                companies = companies[:max_names]
                logger.info(f"Limited to {max_names} companies")
            
            logger.info(f"Processing {len(companies)} companies\n")
            
            results = []
            if os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        results = json.load(f)
                    logger.info(f"Loaded {len(results)} existing results\n")
                except json.JSONDecodeError:
                    logger.warning(f"Could not read existing results, starting fresh\n")
                    results = []
            
            processed_companies = {r['company'] for r in results}
            
            companies_to_process = [c for c in companies if c not in processed_companies]
            
            if not companies_to_process:
                logger.info("All companies already processed")
                perf_metrics = self.performance_tracker.end_batch()
                return {
                    "processed": len(companies),
                    "found": sum(1 for r in results if r.get('base_url') is not None),
                    "not_found": sum(1 for r in results if r.get('base_url') is None),
                    "performance": perf_metrics
                }
            
            logger.info(f"Processing {len(companies_to_process)} new companies\n")
            
            found_count = 0
            not_found_count = 0
            
            for i, company_name in enumerate(companies_to_process, 1):
                logger.info(f"[{i}/{len(companies_to_process)}] Searching for: {company_name}")
                
                try:
                    result = self.google_search(company_name)
                    
                    if result['base_url']:
                        logger.info(f"  ✓ Base URL: {result['base_url']}")
                        if result['sub_urls']:
                            logger.info(f"  ✓ Sub URLs found: {len(result['sub_urls'])}")
                            for idx, url in enumerate(result['sub_urls'], 1):
                                logger.info(f"    {idx}. {url}")
                        if result['additional_urls']:
                            logger.info(f"  ✓ Additional URLs found: {len(result['additional_urls'])}")
                            for idx, url in enumerate(result['additional_urls'], 1):
                                logger.info(f"    {idx}. {url}")
                        
                        results.append({
                            "company": company_name,
                            "base_url": result['base_url'],
                            "sub_urls": result['sub_urls'],
                            "additional_urls": result['additional_urls'],
                            "status": "found",
                            "total_urls": 1 + len(result['sub_urls']) + len(result['additional_urls'])
                        })
                        found_count += 1
                    else:
                        logger.info(f"  ✗ No website found, skipping...")
                        results.append({
                            "company": company_name,
                            "base_url": None,
                            "sub_urls": [],
                            "additional_urls": [],
                            "status": "not_found",
                            "total_urls": 0
                        })
                        not_found_count += 1
                    
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=2, ensure_ascii=False)
                    
                    if i < len(companies_to_process):
                        time.sleep(1.5)
                
                except Exception as e:
                    logger.error(f"  ✗ Error processing company '{company_name}': {e}")
                    results.append({
                        "company": company_name,
                        "base_url": None,
                        "sub_urls": [],
                        "additional_urls": [],
                        "status": "error",
                        "error": str(e),
                        "total_urls": 0
                    })
                    not_found_count += 1
            
            perf_metrics = self.performance_tracker.end_batch()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"✓ Results saved to {output_file}")
            logger.info(f"Summary: Found {found_count}, Not found {not_found_count}")
            logger.info(f"{'='*60}\n")
            
            return {
                "processed": len(companies_to_process),
                "found": found_count,
                "not_found": not_found_count,
                "performance": perf_metrics
            }
        
        finally:
            self._close_driver()


def main():
    searcher = SeleniumGoogleSearcher(headless=False)
    
    input_file = "company_namess.json"
    output_file = "company_urls.json"
    
    try:
        result = searcher.process_companies(
            input_file=input_file,
            output_file=output_file,
            max_names=MAX_NAMES_TO_SEARCH
        )
        
        print(f"\n{'='*60}")
        print(f"Processing complete!")
        print(f"Processed: {result['processed']}")
        print(f"Found: {result['found']}")
        print(f"Not found: {result['not_found']}")
        
        if 'performance' in result:
            perf = result['performance']
            print(f"\nPerformance Metrics:")
            print(f"Total Duration: {perf['total_duration_seconds']:.2f} seconds")
            print(f"Average per Company: {perf['average_time_per_company']:.2f} seconds")
        
        print(f"{'='*60}")
    
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        print(f"\nAn error occurred: {e}")


if __name__ == "__main__":
    main()
