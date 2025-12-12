"""
Companies Database Manager
Handles all database operations for Company URL Finder
Manages: companies, company_sub_urls, company_additional_urls tables
"""

import os
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dotenv import load_dotenv
from mysql.connector import Error

# Parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_connection, get_cursor, execute_query
from utils.url_utils import detect_url_label

load_dotenv()
logger = logging.getLogger(__name__)


class CompaniesDB:
    """Manages company URL finder database operations"""
    
    def __init__(self):
        """Initialize companies database manager"""
        self.json_file = os.getenv('COMPANIES_JSON_FILE')
    
    def create_tables(self) -> bool:
        """Create all required tables for company URL finder"""
        try:
            logger.info("📋 Creating company tables...")
            
            with get_cursor() as cursor:
                # Table 1: Companies (main table)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS companies (
                        company_id INT AUTO_INCREMENT PRIMARY KEY,
                        company_name VARCHAR(500) NOT NULL UNIQUE,
                        base_url VARCHAR(2048) DEFAULT NULL,
                        status VARCHAR(50) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_company_name (company_name),
                        INDEX idx_status (status)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'companies' created/verified")

                # Table 2: Company Sub URLs
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_sub_urls (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        company_id INT NOT NULL,
                        company_name VARCHAR(500) NOT NULL,
                        sub_url VARCHAR(2048) NOT NULL,
                        label VARCHAR(100) DEFAULT 'Other',
                        form BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
                        INDEX idx_company_id (company_id),
                        INDEX idx_label (label),
                        INDEX idx_company_name (company_name),
                        INDEX idx_sub_url (sub_url(255)),
                        INDEX idx_form (form)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'company_sub_urls' created/verified")
                
                # Table 3: Company Additional URLs
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS company_additional_urls (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        company_id INT NOT NULL,
                        company_name VARCHAR(500) NOT NULL,
                        additional_url VARCHAR(2048) NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
                        INDEX idx_company_id (company_id),
                        INDEX idx_company_name (company_name)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("  ✓ Table 'company_additional_urls' created/verified")
            
            logger.info("✓ All company tables created successfully!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error creating tables: {e}")
            return False
    
    def load_companies_from_json(self, json_file: str = None) -> bool:
        """
        Load company names from JSON file into database
        
        Args:
            json_file: Path to JSON file (uses .env if not provided)
            
        Returns:
            bool: True if successful
        """
        try:
            if json_file is None:
                json_file = self.json_file
                if not json_file:
                    logger.error("✗ COMPANIES_JSON_FILE not set in .env")
                    return False
                logger.info(f"📄 Using JSON file from .env: {json_file}")
            
            if not os.path.exists(json_file):
                logger.error(f"✗ JSON file not found: {json_file}")
                return False
            
            with open(json_file, 'r', encoding='utf-8') as f:
                companies = json.load(f)
            
            if not companies:
                logger.warning("⚠ JSON file is empty")
                return False
            
            logger.info(f"📥 Loading {len(companies)} companies from JSON...")
            
            inserted = 0
            skipped = 0
            
            with get_cursor() as cursor:
                for company_name in companies:
                    try:
                        cursor.execute("""
                            INSERT INTO companies (company_name, base_url, status)
                            VALUES (%s, NULL, 'pending')
                            ON DUPLICATE KEY UPDATE company_name = company_name
                        """, (company_name,))
                        
                        if cursor.rowcount > 0:
                            inserted += 1
                            logger.info(f"  ✓ Inserted: {company_name}")
                        else:
                            skipped += 1
                            logger.info(f"  ⊘ Skipped (duplicate): {company_name}")
                    
                    except Error as e:
                        logger.error(f"  ✗ Error inserting '{company_name}': {e}")
                        continue
            
            logger.info(f"\n✓ Loading complete! Inserted: {inserted}, Skipped: {skipped}\n")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"✗ Invalid JSON: {e}")
            return False
        except Error as e:
            logger.error(f"✗ Database error: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error: {e}")
            return False
    
    def get_pending_companies(self, limit: int = None) -> List[Tuple[int, str]]:
        """
        Get companies that need URL scraping
        
        Args:
            limit: Maximum number of companies to return
            
        Returns:
            List of tuples: [(company_id, company_name), ...]
        """
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
            
            # Return list of tuples (company_id, company_name)
            return [(row[0], row[1]) for row in results]
            
        except Error as e:
            logger.error(f"✗ Error fetching pending companies: {e}")
            return []
    
    def update_company_status(self, company_id: int, company_name: str, base_url: str, status: str) -> bool:
        """
        Update company status and base URL
        
        Args:
            company_id: Company ID
            company_name: Company name (for logging)
            base_url: Base URL if found (or None)
            status: New status (found/not_found/error)
            
        Returns:
            bool: True if successful
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE companies
                    SET status = %s, base_url = %s
                    WHERE company_id = %s
                """, (status, base_url, company_id))
            
            return True
            
        except Error as e:
            logger.error(f"✗ Error updating company {company_id}: {e}")
            return False

    def insert_sub_urls(self, company_id: int, company_name: str, sub_urls: List[str]) -> bool:
        """
        Insert sub URLs for a company with auto-detected labels
        
        Args:
            company_id: Company ID
            company_name: Company name
            sub_urls: List of URL strings
            
        Returns:
            bool: True if successful
        """
        try:
            if not sub_urls:
                return True
            
            # Detect labels for each URL
            data = [(company_id, company_name, url, detect_url_label(url)) for url in sub_urls]
            
            with get_cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO company_sub_urls (company_id, company_name, sub_url, label)
                    VALUES (%s, %s, %s, %s)
                """, data)
            
            logger.debug(f"  ✓ Inserted {len(sub_urls)} sub URLs for {company_name}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error inserting sub URLs: {e}")
            return False
    
    def insert_additional_urls(self, company_id: int, company_name: str, additional_urls: List[str]) -> bool:
        """
        Insert additional URLs for a company
        
        Args:
            company_id: Company ID
            company_name: Company name
            additional_urls: List of URL strings
            
        Returns:
            bool: True if successful
        """
        try:
            if not additional_urls:
                return True
            
            data = [(company_id, company_name, url) for url in additional_urls]
            
            with get_cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO company_additional_urls (company_id, company_name, additional_url)
                    VALUES (%s, %s, %s)
                """, data)
            
            logger.debug(f"  ✓ Inserted {len(additional_urls)} additional URLs for {company_name}")
            return True
            
        except Error as e:
            logger.error(f"✗ Error inserting additional URLs: {e}")
            return False
    
    def get_sub_urls(self, company_id: int) -> List[Dict]:
        """
        Get all sub URLs for a specific company
        
        Args:
            company_id: Company ID to fetch sub URLs for
            
        Returns:
            List of dictionaries containing sub URL data:
            [
                {
                    'id': int,
                    'company_id': int,
                    'company_name': str,
                    'sub_url': str,
                    'label': str,
                    'form': bool,
                    'created_at': datetime
                },
                ...
            ]
        """
        try:
            query = """
                SELECT 
                    id,
                    company_id,
                    company_name,
                    sub_url,
                    label,
                    form,
                    created_at
                FROM company_sub_urls
                WHERE company_id = %s
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
                    'company_name': row[2],
                    'sub_url': row[3],
                    'label': row[4],
                    'form': bool(row[5]),
                    'created_at': row[6]
                })
            
            logger.debug(f"Retrieved {len(sub_urls)} sub URLs for company_id {company_id}")
            return sub_urls
            
        except Error as e:
            logger.error(f"✗ Error fetching sub URLs for company_id {company_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"✗ Unexpected error fetching sub URLs: {e}")
            return []

    def update_sub_url_form(self, sub_url: str, has_form: bool) -> bool:
        """
        Update the form column for a specific sub URL
        Handles trailing slash differences by normalizing URLs
        
        Args:
            sub_url: The sub URL to update
            has_form: True if form found on this URL, False otherwise
            
        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            form_value = 1 if has_form else 0
            

            normalized_input = sub_url.rstrip('/').lower()
            
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE company_sub_urls
                    SET form = %s
                    WHERE LOWER(TRIM(TRAILING '/' FROM sub_url)) = %s
                """, (form_value, normalized_input))
                
                rows_affected = cursor.rowcount
                
                if rows_affected > 0:
                    logger.debug(f"✓ Updated form={form_value} for sub_url: {sub_url} ({rows_affected} row(s))")
                    return True
                else:
                    logger.warning(f"⚠ No matching sub_url found to update: {sub_url}")
                    logger.warning(f"   Normalized to: {normalized_input}")
                    return False
            
        except Error as e:
            logger.error(f"✗ Error updating form column for {sub_url}: {e}")
            return False
        except Exception as e:
            logger.error(f"✗ Unexpected error updating form column: {e}")
            return False

    def get_statistics(self) -> Dict:
        """
        Get database statistics
        
        Returns:
            Dict with statistics
        """
        try:
            stats = {}
            
            with get_cursor() as cursor:
                # Total companies
                cursor.execute("SELECT COUNT(*) FROM companies")
                stats['total_companies'] = cursor.fetchone()[0]
                
                # By status
                cursor.execute("""
                    SELECT status, COUNT(*) 
                    FROM companies 
                    GROUP BY status
                """)
                for row in cursor.fetchall():
                    stats[row[0]] = row[1]
                
                # Sub URLs
                cursor.execute("SELECT COUNT(*) FROM company_sub_urls")
                stats['total_sub_urls'] = cursor.fetchone()[0]
                
                # Additional URLs
                cursor.execute("SELECT COUNT(*) FROM company_additional_urls")
                stats['total_additional_urls'] = cursor.fetchone()[0]
            
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
            logger.info(f"  📊 Sub URLs: {stats.get('total_sub_urls', 0)}")
            logger.info(f"  📊 Additional URLs: {stats.get('total_additional_urls', 0)}")
            
            # Sample companies
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT company_id, company_name, base_url, status 
                    FROM companies 
                    LIMIT 5
                """)
                
                logger.info("\n  📋 Sample companies:")
                for row in cursor.fetchall():
                    base_url = row[2] if row[2] else "Not scraped yet"
                    logger.info(f"    ID {row[0]}: {row[1]}")
                    logger.info(f"           URL: {base_url}")
                    logger.info(f"           Status: {row[3]}")
            
            logger.info("\n✓ Verification complete!\n")
            return True
            
        except Error as e:
            logger.error(f"✗ Error verifying setup: {e}")
            return False
    
    def reset_database(self) -> bool:
        """Drop all company tables (USE WITH CAUTION!)"""
        try:
            logger.warning("\n⚠️  RESETTING DATABASE - ALL DATA WILL BE DELETED!")
            
            response = input("Type 'YES' to confirm: ")
            if response != 'YES':
                logger.info("Reset cancelled.")
                return False
            
            with get_cursor() as cursor:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                
                tables = ['company_additional_urls', 'company_sub_urls', 'companies']
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
    # Setup logging for standalone execution
    import sys
    from pathlib import Path
    
    # Get log directory
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
