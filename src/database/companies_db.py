"""
Companies Database Manager
Handles all database operations for Company URL Finder
Manages: companies, urls tables (unified structure)
"""

import os
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from mysql.connector import Error

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_connection, get_cursor, execute_query
from utils.url_utils import detect_url_label

load_dotenv()
logger = logging.getLogger(__name__)

PRODUCT_PAGE_LABEL = 'products page'


class CompaniesDB:
    """Manages company URL finder database operations"""
    
    def __init__(self):
        """Initialize companies database manager"""
        self.json_file = os.getenv('COMPANIES_JSON_FILE')
    
    def create_tables(self) -> bool:
        """Create all required tables for company URL finder - unified structure"""
        try:
            logger.info("📋 Creating company tables...")
            
            with get_cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS companies (
                        company_id INT AUTO_INCREMENT PRIMARY KEY,
                        company_name VARCHAR(500) NOT NULL UNIQUE,
                        status VARCHAR(50) DEFAULT 'pending',
                        contact_scraped TINYINT(1) DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_company_name (company_name),
                        INDEX idx_status (status),
                        INDEX idx_contact_scraped (contact_scraped)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'companies' ready")

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS urls (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        company_id INT DEFAULT NULL,
                        url VARCHAR(2048) NOT NULL UNIQUE,
                        category ENUM('base', 'sub', 'additional') DEFAULT NULL,
                        label VARCHAR(100) DEFAULT NULL,
                        form TINYINT(1) DEFAULT 0,
                        product VARCHAR(255) DEFAULT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
                        INDEX idx_company_id (company_id),
                        INDEX idx_url (url(255)),
                        INDEX idx_category (category),
                        INDEX idx_label (label),
                        INDEX idx_form (form),
                        INDEX idx_product (product),
                        INDEX idx_category_form (category, form)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'urls' ready")
            
            logger.info("✓ Database tables ready\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error creating tables: {e}")
            return False
    
    def load_companies_from_json(self, json_file: str = None) -> bool:
        """Load company names from JSON file into database"""
        try:
            if json_file is None:
                json_file = self.json_file
                if not json_file:
                    logger.error("✗ COMPANIES_JSON_FILE not set in .env")
                    return False
            
            if not os.path.exists(json_file):
                logger.error(f"✗ JSON file not found: {json_file}")
                return False
            
            with open(json_file, 'r', encoding='utf-8') as f:
                companies = json.load(f)
            
            if not companies:
                logger.warning("⚠ JSON file is empty")
                return False
            
            logger.info(f"📥 Loading {len(companies)} companies...")
            
            inserted = 0
            skipped = 0
            
            with get_cursor() as cursor:
                for company_name in companies:
                    try:
                        cursor.execute("""
                            INSERT INTO companies (company_name, status)
                            VALUES (%s, 'pending')
                            ON DUPLICATE KEY UPDATE company_name = company_name
                        """, (company_name,))
                        
                        if cursor.rowcount > 0:
                            inserted += 1
                        else:
                            skipped += 1
                    
                    except Error as e:
                        logger.error(f"  ✗ Error inserting '{company_name}': {e}")
                        continue
            
            logger.info(f"✓ Loaded: {inserted} new, {skipped} existing\n")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"✗ Invalid JSON: {e}")
            return False
        except Error as e:
            logger.error(f"✗ Database error: {e}")
            return False
    
    def get_pending_companies(self, limit: int = None) -> List[Tuple[int, str]]:
        """Get companies that need URL scraping"""
        try:
            query = """
                SELECT company_id, company_name
                FROM companies
                WHERE status = 'pending'
                ORDER BY company_id
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            results = execute_query(query, fetch=True)
            return [(row[0], row[1]) for row in results]
            
        except Error as e:
            logger.error(f"✗ Error fetching pending companies: {e}")
            return []
    
    def update_company_status(self, company_id: int, base_url: str, status: str) -> bool:
        """Update company status and insert base URL into urls table"""
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE companies
                    SET status = %s
                    WHERE company_id = %s
                """, (status, company_id))
                
                if base_url:
                    cursor.execute("""
                        INSERT INTO urls (company_id, url, category, label, form)
                        VALUES (%s, %s, 'base', 'base', 0)
                        ON DUPLICATE KEY UPDATE url = VALUES(url)
                    """, (company_id, base_url))
            
            return True
            
        except Error as e:
            logger.error(f"✗ Error updating company {company_id}: {e}")
            return False

    def insert_sub_urls(self, company_id: int, sub_urls: List[str]) -> bool:
        """Insert sub URLs for a company into urls table"""
        try:
            if not sub_urls:
                return True
            
            data = [(company_id, url, 'sub', detect_url_label(url), 0) for url in sub_urls]
            
            with get_cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO urls (company_id, url, category, label, form)
                    VALUES (%s, %s, %s, %s, %s)
                """, data)
            
            logger.debug(f"  ✓ Inserted {len(sub_urls)} sub URLs for company_id {company_id}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error inserting sub URLs: {e}")
            return False

    def insert_additional_urls(self, company_id: int, additional_urls: List[str]) -> bool:
        """Insert additional URLs for a company into urls table"""
        try:
            if not additional_urls:
                return True
            
            data = [(company_id, url, 'additional', 'none', 0) for url in additional_urls]
            
            with get_cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO urls (company_id, url, category, label, form)
                    VALUES (%s, %s, %s, %s, %s)
                """, data)
            
            logger.debug(f"  ✓ Inserted {len(additional_urls)} additional URLs for company_id {company_id}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error inserting additional URLs: {e}")
            return False
    
    def get_sub_urls(self, company_id: int) -> List[Dict]:
        """Get all sub URLs for a specific company from urls table"""
        try:
            query = """
                SELECT 
                    id,
                    company_id,
                    url,
                    label,
                    form,
                    created_at
                FROM urls
                WHERE company_id = %s AND category = 'sub'
                ORDER BY id ASC
            """
            
            results = execute_query(query, (company_id,), fetch=True)
            
            if not results:
                logger.debug(f"No sub URLs found for company_id {company_id}")
                return []
            
            sub_urls = []
            for row in results:
                sub_urls.append({
                    'id': row[0],
                    'company_id': row[1],
                    'url': row[2],
                    'label': row[3],
                    'form': bool(row[4]),
                    'created_at': row[5]
                })
            
            logger.debug(f"Retrieved {len(sub_urls)} sub URLs for company_id {company_id}")
            return sub_urls
            
        except Error as e:
            logger.error(f"✗ Error fetching sub URLs for company_id {company_id}: {e}")
            return []

    def update_sub_url_form(self, sub_url: str, has_form: bool) -> bool:
        """Update the form column for a specific URL in urls table"""
        try:
            form_value = 1 if has_form else 0
            normalized_input = sub_url.rstrip('/').lower()
            
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE urls
                    SET form = %s
                    WHERE LOWER(TRIM(TRAILING '/' FROM url)) = %s
                """, (form_value, normalized_input))
                
                rows_affected = cursor.rowcount
                
                if rows_affected > 0:
                    logger.debug(f"✓ Updated form={form_value} for URL: {sub_url}")
                    return True
                else:
                    logger.warning(f"⚠ No matching URL found: {sub_url}")
                    return False
            
        except Error as e:
            logger.error(f"✗ Error updating form column for {sub_url}: {e}")
            return False

    def get_base_url(self, company_id: int) -> Optional[str]:
        """Get base URL for a specific company"""
        try:
            query = """
                SELECT url
                FROM urls
                WHERE company_id = %s AND category = 'base'
                LIMIT 1
            """
            
            results = execute_query(query, (company_id,), fetch=True)
            
            if results and len(results) > 0:
                return results[0][0]
            return None
            
        except Error as e:
            logger.error(f"✗ Error fetching base URL for company_id {company_id}: {e}")
            return None

    def save_product_page(self, shop_url: str, product_url: str) -> bool:
        """Save product page URL to database"""
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO urls (company_id, url, category, label, product, form)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE product = VALUES(product)
                """, (None, product_url, None, None, PRODUCT_PAGE_LABEL, 0))
            
            logger.debug(f"✓ Saved product page: {product_url}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error saving product page for {shop_url}: {e}")
            return False

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        try:
            stats = {}
            
            with get_cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM companies")
                stats['total_companies'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM companies 
                    GROUP BY status
                """)
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]
                
                cursor.execute("SELECT COUNT(*) FROM urls")
                stats['total_urls'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT category, COUNT(*) 
                    FROM urls 
                    WHERE category IS NOT NULL
                    GROUP BY category
                """)
                for row in cursor.fetchall():
                    stats[f'{row[0]}_urls'] = row[1]
                
                cursor.execute("SELECT COUNT(*) FROM urls WHERE form = 1")
                stats['urls_with_forms'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM urls WHERE product IS NOT NULL")
                stats['product_urls'] = cursor.fetchone()[0]
            
            return stats
            
        except Error as e:
            logger.error(f"✗ Error getting statistics: {e}")
            return {}
    
    def verify_setup(self) -> bool:
        """Verify database setup and show statistics"""
        try:
            logger.info("\n🔍 Verifying database setup...\n")
            
            stats = self.get_statistics()
            
            logger.info(f"  📊 Companies: {stats.get('total_companies', 0)}")
            logger.info(f"      └─ Pending: {stats.get('pending', 0)}")
            logger.info(f"      └─ Found: {stats.get('found', 0)}")
            logger.info(f"      └─ Not found: {stats.get('not_found', 0)}")
            logger.info(f"      └─ Error: {stats.get('error', 0)}")
            logger.info(f"  📊 Total URLs: {stats.get('total_urls', 0)}")
            logger.info(f"      └─ Base URLs: {stats.get('base_urls', 0)}")
            logger.info(f"      └─ Sub URLs: {stats.get('sub_urls', 0)}")
            logger.info(f"      └─ Additional URLs: {stats.get('additional_urls', 0)}")
            logger.info(f"  📊 URLs with forms: {stats.get('urls_with_forms', 0)}")
            logger.info(f"  📊 Product URLs: {stats.get('product_urls', 0)}")
            
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT c.company_id, c.company_name, u.url, c.status 
                    FROM companies c
                    LEFT JOIN urls u ON c.company_id = u.company_id AND u.category = 'base'
                    LIMIT 5
                """)
                
                logger.info("\n  📋 Sample companies:")
                for row in cursor.fetchall():
                    base_url = row[2] if row[2] else "Not scraped yet"
                    logger.info(f"    ID {row[0]}: {row[1]} | {base_url} | {row[3]}")
                
                cursor.execute("""
                    SELECT id, url, product, created_at
                    FROM urls
                    WHERE product IS NOT NULL
                    LIMIT 5
                """)
                
                if cursor.rowcount > 0:
                    logger.info("\n  📋 Sample product URLs:")
                    for row in cursor.fetchall():
                        logger.info(f"    ID {row[0]}: {row[1]} | {row[2]} | {row[3]}")
            
            logger.info("\n✓ Verification complete!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error verifying setup: {e}")
            return False
    
    def reset_database(self) -> bool:
        """Drop all company tables"""
        try:
            logger.warning("\n⚠️  RESETTING DATABASE - ALL DATA WILL BE DELETED!")
            
            response = input("Type 'YES' to confirm: ")
            if response != 'YES':
                logger.info("Reset cancelled.")
                return False
            
            with get_cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                tables = ['urls', 'companies']
                for table in tables:
                    cursor.execute(f"DROP TABLE IF EXISTS {table}")
                    logger.info(f"  ✓ Dropped table: {table}")
                
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            logger.info("\n✓ Database reset complete!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error resetting database: {e}")
            return False


def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("  COMPANIES DATABASE SETUP")
    print("=" * 70 + "\n")
    
    db = CompaniesDB()
    
    try:
        print("\nWhat would you like to do?")
        print("1. Create tables and load data")
        print("2. Only create tables")
        print("3. Only load data from JSON")
        print("4. Verify current setup")
        print("5. Reset database (DELETE ALL DATA)")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-5): ").strip()
        
        if choice == '1':
            if db.create_tables():
                db.load_companies_from_json()
                db.verify_setup()
        
        elif choice == '2':
            db.create_tables()
            db.verify_setup()
        
        elif choice == '3':
            db.load_companies_from_json()
            db.verify_setup()
        
        elif choice == '4':
            db.verify_setup()
        
        elif choice == '5':
            if db.reset_database():
                db.create_tables()
        
        elif choice == '0':
            logger.info("Exiting...")
        
        else:
            logger.warning("Invalid choice!")
    
    except KeyboardInterrupt:
        logger.info("\n\nCancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    CURRENT_FILE_DIR = Path(__file__).parent
    AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent
    LOG_DIR = AUTOMATION_ROOT / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / 'companies_db.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    main()
