"""
ClickUp Database Manager
Database operations for ClickUp ticket data
Handles tickets, API keys, and sync history
"""

import os
import sys
import logging
import json
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.connection import get_cursor

logger = logging.getLogger(__name__)


class ClickUpDB:
    """
    ClickUp Database Manager
    
    Manages three main tables:
    1. clickup_api_keys - Store multiple ClickUp API tokens
    2. clickup_tickets - Store parsed ticket/task data
    3. clickup_sync_log - Track synchronization history
    """
    
    def __init__(self):
        """Initialize ClickUp database manager"""
        logger.info("Initializing ClickUp database manager")
    
    def create_tables(self) -> bool:
        """
        Create all required tables for ClickUp integration
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                
                # ============================================================
                # TABLE 1: clickup_api_keys
                # ============================================================
                logger.info("Creating clickup_api_keys table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clickup_api_keys (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        api_key VARCHAR(255) NOT NULL UNIQUE,
                        key_name VARCHAR(100) NOT NULL,
                        workspace_id VARCHAR(50),
                        workspace_name VARCHAR(255),
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used_at TIMESTAMP NULL,
                        last_sync_at TIMESTAMP NULL,
                        total_syncs INT DEFAULT 0,
                        notes TEXT,
                        INDEX idx_active (is_active),
                        INDEX idx_workspace (workspace_id)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("✓ clickup_api_keys table created")
                
                # ============================================================
                # TABLE 2: clickup_tickets
                # ============================================================
                logger.info("Creating clickup_tickets table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clickup_tickets (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        api_key_id INT NOT NULL,
                        
                        -- ClickUp IDs
                        ticket_id VARCHAR(50) NOT NULL UNIQUE,
                        workspace_id VARCHAR(50),
                        space_id VARCHAR(50),
                        list_id VARCHAR(50),
                        
                        -- ClickUp Names
                        workspace_name VARCHAR(255),
                        space_name VARCHAR(255),
                        list_name VARCHAR(255),
                        
                        -- Ticket Core Data
                        name VARCHAR(500) NOT NULL,
                        description TEXT,
                        status VARCHAR(100),
                        priority VARCHAR(50),
                        
                        -- Dates
                        due_date BIGINT,
                        start_date BIGINT,
                        date_created BIGINT,
                        date_updated BIGINT,
                        date_closed BIGINT,
                        
                        -- Assignment
                        assignees JSON,
                        creator_id VARCHAR(50),
                        creator_username VARCHAR(100),
                        
                        -- Organization
                        tags JSON,
                        custom_fields JSON,
                        
                        -- URLs
                        url VARCHAR(500),
                        
                        -- Metadata
                        archived BOOLEAN DEFAULT FALSE,
                        time_estimate BIGINT,
                        time_spent BIGINT,
                        
                        -- Tracking
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        
                        FOREIGN KEY (api_key_id) REFERENCES clickup_api_keys(id) ON DELETE CASCADE,
                        INDEX idx_ticket_id (ticket_id),
                        INDEX idx_workspace (workspace_id),
                        INDEX idx_space (space_id),
                        INDEX idx_list (list_id),
                        INDEX idx_status (status),
                        INDEX idx_priority (priority),
                        INDEX idx_archived (archived),
                        INDEX idx_date_created (date_created),
                        INDEX idx_date_updated (date_updated)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("✓ clickup_tickets table created")
                
                # ============================================================
                # TABLE 3: clickup_sync_log
                # ============================================================
                logger.info("Creating clickup_sync_log table...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS clickup_sync_log (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        api_key_id INT NOT NULL,
                        sync_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        sync_completed_at TIMESTAMP NULL,
                        status ENUM('running', 'completed', 'failed') DEFAULT 'running',
                        tickets_fetched INT DEFAULT 0,
                        tickets_new INT DEFAULT 0,
                        tickets_updated INT DEFAULT 0,
                        error_message TEXT,
                        
                        FOREIGN KEY (api_key_id) REFERENCES clickup_api_keys(id) ON DELETE CASCADE,
                        INDEX idx_api_key (api_key_id),
                        INDEX idx_status (status),
                        INDEX idx_sync_date (sync_started_at)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """)
                logger.info("✓ clickup_sync_log table created")
                
                logger.info("✓ All ClickUp tables created successfully")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error creating tables: {e}")
            return False
    
    def drop_tables(self) -> bool:
        """
        Drop all ClickUp tables (use with caution!)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                logger.warning("Dropping ClickUp tables...")
                
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute("DROP TABLE IF EXISTS clickup_sync_log")
                cursor.execute("DROP TABLE IF EXISTS clickup_tickets")
                cursor.execute("DROP TABLE IF EXISTS clickup_api_keys")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                
                logger.info("✓ All ClickUp tables dropped")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error dropping tables: {e}")
            return False
    
    def insert_api_key(
        self,
        api_key: str,
        key_name: str,
        workspace_id: Optional[str] = None,
        workspace_name: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Optional[int]:
        """
        Insert a new ClickUp API key
        
        Args:
            api_key: ClickUp API token
            key_name: Friendly name for this key
            workspace_id: ClickUp workspace ID
            workspace_name: ClickUp workspace name
            notes: Optional notes about this key
        
        Returns:
            API key ID if successful, None otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO clickup_api_keys 
                    (api_key, key_name, workspace_id, workspace_name, notes)
                    VALUES (%s, %s, %s, %s, %s)
                """, (api_key, key_name, workspace_id, workspace_name, notes))
                
                api_key_id = cursor.lastrowid
                logger.info(f"✓ API key '{key_name}' inserted (ID: {api_key_id})")
                return api_key_id
                
        except Exception as e:
            logger.error(f"✗ Error inserting API key: {e}")
            return None
    
    def get_active_api_keys(self) -> List[Dict[str, Any]]:
        """
        Get all active API keys
        
        Returns:
            List of API key dictionaries
        """
        try:
            with get_cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT 
                        id,
                        api_key,
                        key_name,
                        workspace_id,
                        workspace_name,
                        created_at,
                        last_used_at,
                        last_sync_at,
                        total_syncs
                    FROM clickup_api_keys
                    WHERE is_active = TRUE
                    ORDER BY key_name
                """)
                
                keys = cursor.fetchall()
                logger.info(f"✓ Found {len(keys)} active API key(s)")
                return keys
                
        except Exception as e:
            logger.error(f"✗ Error fetching API keys: {e}")
            return []
    
    def update_api_key_usage(self, api_key_id: int) -> bool:
        """
        Update last_used_at timestamp for an API key
        
        Args:
            api_key_id: API key ID
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE clickup_api_keys
                    SET last_used_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (api_key_id,))
                
                return True
                
        except Exception as e:
            logger.error(f"✗ Error updating API key usage: {e}")
            return False
    
    def deactivate_api_key(self, api_key_id: int) -> bool:
        """
        Deactivate an API key (soft delete)
        
        Args:
            api_key_id: API key ID
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE clickup_api_keys
                    SET is_active = FALSE
                    WHERE id = %s
                """, (api_key_id,))
                
                logger.info(f"✓ API key {api_key_id} deactivated")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error deactivating API key: {e}")
            return False
    
    def insert_ticket(
        self,
        api_key_id: int,
        ticket_data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Insert a new ticket or update if exists
        
        Args:
            api_key_id: API key ID
            ticket_data: Ticket data from ClickUp API
        
        Returns:
            Ticket ID if successful, None otherwise
        """
        try:
            # Extract data from ClickUp API response
            ticket_id = ticket_data.get('id')
            name = ticket_data.get('name', 'Untitled')
            description = ticket_data.get('description', '')
            status = ticket_data.get('status', {}).get('status', 'unknown')
            priority = ticket_data.get('priority', {}).get('priority', 'none') if ticket_data.get('priority') else 'none'
            
            # Dates (ClickUp uses milliseconds)
            due_date = ticket_data.get('due_date')
            start_date = ticket_data.get('start_date')
            date_created = ticket_data.get('date_created')
            date_updated = ticket_data.get('date_updated')
            date_closed = ticket_data.get('date_closed')
            
            # IDs and Names
            workspace_id = ticket_data.get('_workspace_id') or ticket_data.get('team_id')
            workspace_name = ticket_data.get('_workspace_name')
            space_id = ticket_data.get('_space_id') or ticket_data.get('space', {}).get('id')
            space_name = ticket_data.get('_space_name')
            list_id = ticket_data.get('_list_id') or ticket_data.get('list', {}).get('id')
            list_name = ticket_data.get('_list_name')
            
            # Assignees
            assignees = json.dumps(ticket_data.get('assignees', []))
            
            # Creator
            creator = ticket_data.get('creator', {})
            creator_id = creator.get('id')
            creator_username = creator.get('username')
            
            # Tags
            tags = json.dumps(ticket_data.get('tags', []))
            
            # Custom fields
            custom_fields = json.dumps(ticket_data.get('custom_fields', []))
            
            # URL
            url = ticket_data.get('url')
            
            # Metadata
            archived = ticket_data.get('archived', False)
            time_estimate = ticket_data.get('time_estimate')
            time_spent = ticket_data.get('time_spent')
            
            with get_cursor() as cursor:
                # Check if ticket exists
                cursor.execute("""
                    SELECT id FROM clickup_tickets WHERE ticket_id = %s
                """, (ticket_id,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing ticket
                    cursor.execute("""
                        UPDATE clickup_tickets SET
                            api_key_id = %s,
                            workspace_id = %s,
                            space_id = %s,
                            list_id = %s,
                            workspace_name = %s,
                            space_name = %s,
                            list_name = %s,
                            name = %s,
                            description = %s,
                            status = %s,
                            priority = %s,
                            due_date = %s,
                            start_date = %s,
                            date_created = %s,
                            date_updated = %s,
                            date_closed = %s,
                            assignees = %s,
                            creator_id = %s,
                            creator_username = %s,
                            tags = %s,
                            custom_fields = %s,
                            url = %s,
                            archived = %s,
                            time_estimate = %s,
                            time_spent = %s
                        WHERE ticket_id = %s
                    """, (
                        api_key_id, workspace_id, space_id, list_id,
                        workspace_name, space_name, list_name,
                        name, description, status, priority,
                        due_date, start_date, date_created, date_updated, date_closed,
                        assignees, creator_id, creator_username,
                        tags, custom_fields, url, archived,
                        time_estimate, time_spent, ticket_id
                    ))
                    
                    logger.debug(f"✓ Updated ticket: {name}")
                    return existing[0]
                else:
                    # Insert new ticket
                    cursor.execute("""
                        INSERT INTO clickup_tickets (
                            api_key_id, ticket_id,
                            workspace_id, space_id, list_id,
                            workspace_name, space_name, list_name,
                            name, description, status, priority,
                            due_date, start_date, date_created, date_updated, date_closed,
                            assignees, creator_id, creator_username,
                            tags, custom_fields, url, archived,
                            time_estimate, time_spent
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        api_key_id, ticket_id,
                        workspace_id, space_id, list_id,
                        workspace_name, space_name, list_name,
                        name, description, status, priority,
                        due_date, start_date, date_created, date_updated, date_closed,
                        assignees, creator_id, creator_username,
                        tags, custom_fields, url, archived,
                        time_estimate, time_spent
                    ))
                    
                    logger.debug(f"✓ Inserted ticket: {name}")
                    return cursor.lastrowid
                    
        except Exception as e:
            logger.error(f"✗ Error inserting ticket: {e}")
            return None
    
    def get_tickets(
        self,
        api_key_id: Optional[int] = None,
        workspace_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get tickets with optional filters
        
        Args:
            api_key_id: Filter by API key ID
            workspace_id: Filter by workspace ID
            status: Filter by status
            limit: Maximum number of tickets to return
        
        Returns:
            List of ticket dictionaries
        """
        try:
            with get_cursor(dictionary=True) as cursor:
                query = "SELECT * FROM clickup_tickets WHERE 1=1"
                params = []
                
                if api_key_id:
                    query += " AND api_key_id = %s"
                    params.append(api_key_id)
                
                if workspace_id:
                    query += " AND workspace_id = %s"
                    params.append(workspace_id)
                
                if status:
                    query += " AND status = %s"
                    params.append(status)
                
                query += " ORDER BY date_updated DESC"
                
                if limit:
                    query += " LIMIT %s"
                    params.append(limit)
                
                cursor.execute(query, tuple(params))
                tickets = cursor.fetchall()
                
                logger.info(f"✓ Found {len(tickets)} ticket(s)")
                return tickets
                
        except Exception as e:
            logger.error(f"✗ Error fetching tickets: {e}")
            return []
    
    def start_sync(self, api_key_id: int) -> Optional[int]:
        """
        Start a new sync session
        
        Args:
            api_key_id: API key ID
        
        Returns:
            Sync log ID if successful, None otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO clickup_sync_log (api_key_id, status)
                    VALUES (%s, 'running')
                """, (api_key_id,))
                
                sync_id = cursor.lastrowid
                logger.info(f"✓ Sync started (ID: {sync_id})")
                return sync_id
                
        except Exception as e:
            logger.error(f"✗ Error starting sync: {e}")
            return None
    
    def complete_sync(
        self,
        sync_id: int,
        tickets_fetched: int,
        tickets_new: int,
        tickets_updated: int
    ) -> bool:
        """
        Mark sync as completed
        
        Args:
            sync_id: Sync log ID
            tickets_fetched: Total tickets fetched
            tickets_new: New tickets inserted
            tickets_updated: Existing tickets updated
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE clickup_sync_log SET
                        sync_completed_at = CURRENT_TIMESTAMP,
                        status = 'completed',
                        tickets_fetched = %s,
                        tickets_new = %s,
                        tickets_updated = %s
                    WHERE id = %s
                """, (tickets_fetched, tickets_new, tickets_updated, sync_id))
                
                # Update API key sync info
                cursor.execute("""
                    UPDATE clickup_api_keys SET
                        last_sync_at = CURRENT_TIMESTAMP,
                        total_syncs = total_syncs + 1
                    WHERE id = (SELECT api_key_id FROM clickup_sync_log WHERE id = %s)
                """, (sync_id,))
                
                logger.info(f"✓ Sync completed (ID: {sync_id})")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error completing sync: {e}")
            return False
    
    def fail_sync(self, sync_id: int, error_message: str) -> bool:
        """
        Mark sync as failed
        
        Args:
            sync_id: Sync log ID
            error_message: Error description
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    UPDATE clickup_sync_log SET
                        sync_completed_at = CURRENT_TIMESTAMP,
                        status = 'failed',
                        error_message = %s
                    WHERE id = %s
                """, (error_message, sync_id))
                
                logger.info(f"✓ Sync marked as failed (ID: {sync_id})")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error failing sync: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get ClickUp database statistics
        
        Returns:
            Dictionary with statistics
        """
        try:
            with get_cursor(dictionary=True) as cursor:
                stats = {}
                
                # API keys
                cursor.execute("SELECT COUNT(*) as count FROM clickup_api_keys WHERE is_active = TRUE")
                stats['active_api_keys'] = cursor.fetchone()['count']
                
                # Total tickets
                cursor.execute("SELECT COUNT(*) as count FROM clickup_tickets")
                stats['total_tickets'] = cursor.fetchone()['count']
                
                # Tickets by status
                cursor.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM clickup_tickets 
                    GROUP BY status
                    ORDER BY count DESC
                """)
                stats['tickets_by_status'] = cursor.fetchall()
                
                # Recent syncs
                cursor.execute("""
                    SELECT COUNT(*) as count 
                    FROM clickup_sync_log 
                    WHERE sync_started_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                """)
                stats['syncs_last_7_days'] = cursor.fetchone()['count']
                
                # Last sync
                cursor.execute("""
                    SELECT sync_completed_at, status, tickets_fetched
                    FROM clickup_sync_log
                    ORDER BY sync_started_at DESC
                    LIMIT 1
                """)
                last_sync = cursor.fetchone()
                stats['last_sync'] = last_sync if last_sync else None
                
                return stats
                
        except Exception as e:
            logger.error(f"✗ Error getting statistics: {e}")
            return {}
    
    def verify_setup(self) -> bool:
        """
        Verify database setup is correct
        
        Returns:
            True if all tables exist, False otherwise
        """
        try:
            with get_cursor() as cursor:
                tables = ['clickup_api_keys', 'clickup_tickets', 'clickup_sync_log']
                
                for table in tables:
                    cursor.execute(f"SHOW TABLES LIKE '{table}'")
                    if not cursor.fetchone():
                        logger.error(f"✗ Table {table} does not exist")
                        return False
                
                logger.info("✓ All ClickUp tables exist")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error verifying setup: {e}")
            return False


# Module-level test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup logging
    CURRENT_FILE_DIR = Path(__file__).parent
    AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent
    LOG_DIR = AUTOMATION_ROOT / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / 'clickup_db.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print("\n" + "=" * 70)
    print("  CLICKUP DATABASE SETUP")
    print("=" * 70 + "\n")
    
    db = ClickUpDB()
    
    print("Options:")
    print("  1. Create tables")
    print("  2. Verify setup")
    print("  3. Show statistics")
    print("  4. Drop tables (DANGER!)")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == '1':
        print("\nCreating tables...")
        if db.create_tables():
            print("✓ Tables created successfully!\n")
        else:
            print("✗ Failed to create tables\n")
    
    elif choice == '2':
        print("\nVerifying setup...")
        if db.verify_setup():
            print("✓ Setup verified!\n")
            stats = db.get_statistics()
            print("Statistics:")
            print(f"  Active API keys: {stats.get('active_api_keys', 0)}")
            print(f"  Total tickets: {stats.get('total_tickets', 0)}")
        else:
            print("✗ Setup verification failed\n")
    
    elif choice == '3':
        print("\nFetching statistics...")
        stats = db.get_statistics()
        print(f"\nActive API keys: {stats.get('active_api_keys', 0)}")
        print(f"Total tickets: {stats.get('total_tickets', 0)}")
        print(f"Syncs (last 7 days): {stats.get('syncs_last_7_days', 0)}")
        
        if stats.get('tickets_by_status'):
            print("\nTickets by status:")
            for item in stats['tickets_by_status']:
                print(f"  {item['status']}: {item['count']}")
        
        if stats.get('last_sync'):
            print(f"\nLast sync: {stats['last_sync']}")
        print()
    
    elif choice == '4':
        confirm = input("\n⚠️  Are you sure? Type 'DELETE' to confirm: ")
        if confirm == 'DELETE':
            if db.drop_tables():
                print("✓ Tables dropped\n")
            else:
                print("✗ Failed to drop tables\n")
        else:
            print("Cancelled\n")
    
    else:
        print("Invalid choice\n")
