"""
Contact Forms Database Manager
Handles all database operations for Contact Form Scraper
Uses existing companies table + urls + forms tables
"""

import os
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
from dotenv import load_dotenv
from mysql.connector import Error

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_connection, get_cursor, execute_query

load_dotenv()
logger = logging.getLogger(__name__)

class ContactFormsDB:
    """Manages contact form scraper database operations"""
    
    def __init__(self):
        """Initialize contact forms database manager"""
        pass
    
    def add_contact_scraped_column(self) -> bool:
        """Add contact_scraped column to companies table (backward compatibility)"""
        try:
            logger.info("📋 Checking contact_scraped column in companies table...")
            
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'companies'
                      AND COLUMN_NAME = 'contact_scraped'
                """)
                
                exists = cursor.fetchone()[0] > 0
                
                if exists:
                    logger.info("  ⊘ Column 'contact_scraped' already exists")
                    return True
                
                cursor.execute("""
                    ALTER TABLE companies 
                    ADD COLUMN contact_scraped TINYINT(1) DEFAULT 0
                """)
                
                logger.info("  ✓ Column 'contact_scraped' added to companies table")
            
            return True
            
        except Error as e:
            logger.error(f"✗ Error adding contact_scraped column: {e}")
            return False
    
    def create_tables(self) -> bool:
        """Create forms table with hybrid storage (JSON + HTML)"""
        try:
            logger.info("📋 Setting up contact form database...")
            
            if not self.add_contact_scraped_column():
                return False
            
            with get_cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS forms (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        company_id INT NOT NULL,
                        page_url VARCHAR(2048) NOT NULL,
                        method VARCHAR(10) NOT NULL,
                        html_content LONGTEXT DEFAULT NULL,
                        form_data JSON NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
                        INDEX idx_company_id (company_id),
                        INDEX idx_page_url (page_url(255))
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'forms' created/verified")
            
            logger.info("✓ Contact form database setup complete!\n")
            return True
            
        except Error as e:
            if e.errno == 1050:
                logger.info("  ⊘ Table 'forms' already exists")
                logger.info("✓ Contact form database setup complete!\n")
                return True
            else:
                logger.error(f"✗ Error creating tables: {e}")
                return False

    def get_companies_to_scrape(self, limit: int = None, only_unscraped: bool = True) -> List[Dict]:
        """Get companies that need contact form scraping from companies + urls tables"""
        try:
            query = """
                SELECT c.company_id, c.company_name, u.url, c.contact_scraped
                FROM companies c
                INNER JOIN urls u 
                    ON c.company_id = u.company_id 
                    AND u.category = 'base'
                WHERE c.status = 'found'
            """
            
            if only_unscraped:
                query += " AND c.contact_scraped = 0"
            
            query += " ORDER BY c.company_id"
            
            if limit:
                query += f" LIMIT {limit}"
            
            results = execute_query(query, fetch=True)
            
            companies = []
            for row in results:
                companies.append({
                    'company_id': row[0],
                    'company_name': row[1],
                    'url': row[2],
                    'scraped': bool(row[3])
                })
            
            return companies
            
        except Error as e:
            logger.error(f"✗ Error fetching companies to scrape: {e}")
            return []
    
    def mark_company_scraped(self, company_id: int) -> bool:
        """Mark a company as scraped in companies table"""
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE companies
                    SET contact_scraped = 1
                    WHERE company_id = %s
                """, (company_id,))
            
            return True
            
        except Error as e:
            logger.error(f"✗ Error marking company {company_id} as scraped: {e}")
            return False

    def insert_contact_form(self, company_id: int, page_url: str, method: str, 
                           form_data: Dict, html_content: str = None) -> bool:
        """Insert a contact form with hybrid storage (JSON + optional HTML)"""
        try:
            form_json = json.dumps(form_data, ensure_ascii=False)
            
            if html_content and len(html_content) > 1000000:
                logger.warning(f"HTML too large ({len(html_content)} bytes), truncating")
                html_content = html_content[:1000000]
            
            with get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO forms 
                    (company_id, page_url, method, html_content, form_data)
                    VALUES (%s, %s, %s, %s, %s)
                """, (company_id, page_url, method, html_content, form_json))
            
            logger.info(f"  ✓ Inserted contact form for company_id {company_id}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error inserting contact form: {e}")
            return False
    
    def get_contact_forms(self, company_id: int = None) -> List[Dict]:
        """Get contact forms from database with HTML content"""
        try:
            if company_id:
                query = """
                    SELECT id, company_id, page_url, method, html_content, form_data
                    FROM forms
                    WHERE company_id = %s
                """
                results = execute_query(query, (company_id,), fetch=True)
            else:
                query = """
                    SELECT id, company_id, page_url, method, html_content, form_data
                    FROM forms
                """
                results = execute_query(query, fetch=True)
            
            forms = []
            for row in results:
                forms.append({
                    'id': row[0],
                    'company_id': row[1],
                    'page_url': row[2],
                    'method': row[3],
                    'html_content': row[4],
                    'form_data': json.loads(row[5])
                })
            
            return forms
            
        except Error as e:
            logger.error(f"✗ Error fetching contact forms: {e}")
            return []


    def get_statistics(self) -> Dict:
        """Get database statistics"""
        try:
            stats = {}
            
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(DISTINCT c.company_id) 
                    FROM companies c
                    INNER JOIN urls u ON c.company_id = u.company_id AND u.category = 'base'
                    WHERE c.status = 'found'
                """)
                stats['total_companies'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT c.company_id) 
                    FROM companies c
                    INNER JOIN urls u ON c.company_id = u.company_id AND u.category = 'base'
                    WHERE c.status = 'found' AND c.contact_scraped = 1
                """)
                stats['scraped'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT c.company_id) 
                    FROM companies c
                    INNER JOIN urls u ON c.company_id = u.company_id AND u.category = 'base'
                    WHERE c.status = 'found' AND c.contact_scraped = 0
                """)
                stats['pending'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM forms")
                stats['total_forms'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT company_id) FROM forms")
                stats['companies_with_forms'] = cursor.fetchone()[0]
            
            return stats
            
        except Error as e:
            logger.error(f"✗ Error getting statistics: {e}")
            return {}

    def verify_setup(self) -> bool:
        """Verify database setup and show statistics"""
        try:
            logger.info("\n🔍 Verifying contact forms database...\n")
            
            stats = self.get_statistics()
            
            logger.info(f"  📊 Companies available for scraping: {stats.get('total_companies', 0)}")
            logger.info(f"      └─ Scraped: {stats.get('scraped', 0)}")
            logger.info(f"      └─ Pending: {stats.get('pending', 0)}")
            logger.info(f"  📊 Contact forms found: {stats.get('total_forms', 0)}")
            logger.info(f"  📊 Companies with forms: {stats.get('companies_with_forms', 0)}")
            
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT c.company_id, c.company_name, u.url, c.contact_scraped
                    FROM companies c
                    INNER JOIN urls u ON c.company_id = u.company_id AND u.category = 'base'
                    WHERE c.status = 'found'
                    LIMIT 5
                """)
                
                logger.info("\n  📋 Sample companies:")
                for row in cursor.fetchall():
                    status = "✓ Scraped" if row[3] else "⏳ Pending"
                    logger.info(f"    ID {row[0]}: {row[1]}")
                    logger.info(f"           URL: {row[2]}")
                    logger.info(f"           Status: {status}")
            
            logger.info("\n✓ Verification complete!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error verifying setup: {e}")
            return False

    def reset_contact_data(self) -> bool:
        """Reset contact scraping data including form column in urls"""
        try:
            logger.warning("\n⚠️  RESETTING CONTACT SCRAPING DATA!")
            logger.warning("This will:")
            logger.warning("  - Delete all contact forms")
            logger.warning("  - Reset contact_scraped status for all companies")
            logger.warning("  - Reset form column in urls table")
            
            response = input("\nType 'YES' to confirm: ")
            if response != 'YES':
                logger.info("Reset cancelled.")
                return False
            
            with get_cursor() as cursor:
                try:
                    cursor.execute("DROP TABLE IF EXISTS forms")
                    logger.info("  ✓ Dropped table: forms")
                except Error as e:
                    if e.errno == 1051:
                        logger.info("  ⊘ Table 'forms' doesn't exist yet")
                    else:
                        raise
                
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'companies'
                      AND COLUMN_NAME = 'contact_scraped'
                """)
                
                column_exists = cursor.fetchone()[0] > 0
                
                if column_exists:
                    cursor.execute("""
                        UPDATE companies 
                        SET contact_scraped = 0 
                        WHERE contact_scraped = 1
                    """)
                    logger.info(f"  ✓ Reset contact_scraped for {cursor.rowcount} companies")
                else:
                    logger.info("  ⊘ Column 'contact_scraped' doesn't exist yet")
                
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'urls'
                """)
                
                table_exists = cursor.fetchone()[0] > 0
                
                if table_exists:
                    cursor.execute("""
                        UPDATE urls 
                        SET form = 0 
                        WHERE form = 1
                    """)
                    logger.info(f"  ✓ Reset form column for {cursor.rowcount} URLs")
                else:
                    logger.info("  ⊘ Table 'urls' doesn't exist yet")
            
            logger.info("\n✓ Contact data reset complete!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error resetting contact data: {e}")
            return False


def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("  CONTACT FORMS DATABASE SETUP")
    print("=" * 70 + "\n")
    
    db = ContactFormsDB()
    
    try:
        print("\nWhat would you like to do?")
        print("1. Setup database (add column + create table)")
        print("2. Verify current setup")
        print("3. Reset contact scraping data (DELETE ALL CONTACT DATA)")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-3): ").strip()
        
        if choice == '1':
            if db.create_tables():
                db.verify_setup()
        
        elif choice == '2':
            db.verify_setup()
        
        elif choice == '3':
            if db.reset_contact_data():
                db.create_tables()
                db.verify_setup()
        
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
            logging.FileHandler(LOG_DIR / 'contact_forms_db.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    main()
