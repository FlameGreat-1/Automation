"""
ClickUp Setup & Management Script
Interactive tool for managing ClickUp integration
Handles API keys, database setup, and testing
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.clickup_db import ClickUpDB
from clickup.api import ClickUpAPI

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
        logging.FileHandler(LOG_DIR / 'clickup_setup.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ClickUpSetup:
    """
    ClickUp Setup Manager
    Interactive tool for managing ClickUp integration
    """
    
    def __init__(self):
        """Initialize setup manager"""
        self.db = ClickUpDB()
        logger.info("ClickUp Setup Manager initialized")
    
    def setup_database(self) -> bool:
        """
        Setup database tables
        
        Returns:
            True if successful, False otherwise
        """
        print("\n" + "=" * 70)
        print("  DATABASE SETUP")
        print("=" * 70 + "\n")
        
        print("This will create the following tables:")
        print("  1. clickup_api_keys - Store ClickUp API tokens")
        print("  2. clickup_tickets - Store ticket/task data")
        print("  3. clickup_sync_log - Track synchronization history")
        print()
        
        confirm = input("Proceed with database setup? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Setup cancelled.\n")
            return False
        
        print("\nCreating tables...")
        if self.db.create_tables():
            print("✓ Database setup complete!\n")
            return True
        else:
            print("✗ Database setup failed!\n")
            return False
    
    def add_api_key(self) -> bool:
        """
        Add a new ClickUp API key
        
        Returns:
            True if successful, False otherwise
        """
        print("\n" + "=" * 70)
        print("  ADD CLICKUP API KEY")
        print("=" * 70 + "\n")
        
        # Get API key
        print("Enter your ClickUp API token (starts with pk_):")
        api_key = input("API Token: ").strip()
        
        if not api_key:
            print("✗ API token is required\n")
            return False
        
        if not api_key.startswith('pk_'):
            print("✗ Invalid API token. Must start with 'pk_'\n")
            return False
        
        # Get friendly name
        key_name = input("Enter a friendly name for this key: ").strip()
        if not key_name:
            key_name = f"Key_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Optional notes
        notes = input("Enter notes (optional): ").strip() or None
        
        print("\nTesting API connection...")
        
        try:
            # Test the API key
            client = ClickUpAPI(api_key)
            
            if not client.test_connection():
                print("✗ API connection test failed\n")
                return False
            
            # Get workspace info
            teams = client.get_authorized_teams()
            
            if not teams:
                print("⚠ No workspaces found for this API key\n")
                workspace_id = None
                workspace_name = None
            else:
                # Use first workspace
                workspace_id = teams[0]['id']
                workspace_name = teams[0].get('name', 'Unknown')
                
                print(f"\n✓ Connected to workspace: {workspace_name}")
                print(f"  Workspace ID: {workspace_id}")
                
                # Show summary
                summary = client.get_workspace_summary(workspace_id)
                print(f"  Spaces: {summary['total_spaces']}")
                print(f"  Lists: {summary['total_lists']}")
                print(f"  Tasks: {summary['total_tasks']}")
            
            # Save to database
            print("\nSaving API key to database...")
            api_key_id = self.db.insert_api_key(
                api_key=api_key,
                key_name=key_name,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                notes=notes
            )
            
            if api_key_id:
                print(f"✓ API key saved successfully! (ID: {api_key_id})\n")
                return True
            else:
                print("✗ Failed to save API key\n")
                return False
                
        except Exception as e:
            print(f"✗ Error: {e}\n")
            return False
    
    def list_api_keys(self) -> None:
        """List all active API keys"""
        print("\n" + "=" * 70)
        print("  ACTIVE API KEYS")
        print("=" * 70 + "\n")
        
        keys = self.db.get_active_api_keys()
        
        if not keys:
            print("No active API keys found.\n")
            return
        
        for idx, key in enumerate(keys, 1):
            print(f"{idx}. {key['key_name']}")
            print(f"   ID: {key['id']}")
            print(f"   Workspace: {key['workspace_name'] or 'Unknown'}")
            print(f"   Created: {key['created_at']}")
            print(f"   Last Sync: {key['last_sync_at'] or 'Never'}")
            print(f"   Total Syncs: {key['total_syncs']}")
            print()
    
    def deactivate_api_key(self) -> bool:
        """
        Deactivate an API key
        
        Returns:
            True if successful, False otherwise
        """
        print("\n" + "=" * 70)
        print("  DEACTIVATE API KEY")
        print("=" * 70 + "\n")
        
        keys = self.db.get_active_api_keys()
        
        if not keys:
            print("No active API keys found.\n")
            return False
        
        # Show keys
        for idx, key in enumerate(keys, 1):
            print(f"{idx}. {key['key_name']} (ID: {key['id']})")
        
        print()
        choice = input("Enter key number to deactivate (or 0 to cancel): ").strip()
        
        try:
            choice = int(choice)
            if choice == 0:
                print("Cancelled.\n")
                return False
            
            if choice < 1 or choice > len(keys):
                print("✗ Invalid choice\n")
                return False
            
            selected_key = keys[choice - 1]
            
            confirm = input(f"Deactivate '{selected_key['key_name']}'? (yes/no): ").strip().lower()
            
            if confirm != 'yes':
                print("Cancelled.\n")
                return False
            
            if self.db.deactivate_api_key(selected_key['id']):
                print(f"✓ API key '{selected_key['key_name']}' deactivated\n")
                return True
            else:
                print("✗ Failed to deactivate API key\n")
                return False
                
        except ValueError:
            print("✗ Invalid input\n")
            return False
    
    def test_api_connection(self) -> None:
        """Test API connection for all active keys"""
        print("\n" + "=" * 70)
        print("  TEST API CONNECTIONS")
        print("=" * 70 + "\n")
        
        keys = self.db.get_active_api_keys()
        
        if not keys:
            print("No active API keys found.\n")
            return
        
        for key in keys:
            print(f"Testing: {key['key_name']}...")
            
            try:
                client = ClickUpAPI(key['api_key'])
                
                if client.test_connection():
                    print(f"  ✓ Connection successful")
                    
                    # Update last used
                    self.db.update_api_key_usage(key['id'])
                else:
                    print(f"  ✗ Connection failed")
                    
            except Exception as e:
                print(f"  ✗ Error: {e}")
            
            print()

    
    def show_statistics(self) -> None:
        """Show database statistics"""
        print("\n" + "=" * 70)
        print("  CLICKUP DATABASE STATISTICS")
        print("=" * 70 + "\n")
        
        stats = self.db.get_statistics()
        
        print(f"Active API Keys: {stats.get('active_api_keys', 0)}")
        print(f"Total Tickets: {stats.get('total_tickets', 0)}")
        print(f"Syncs (Last 7 Days): {stats.get('syncs_last_7_days', 0)}")
        
        # Tickets by status
        tickets_by_status = stats.get('tickets_by_status', [])
        if tickets_by_status:
            print("\nTickets by Status:")
            for item in tickets_by_status:
                print(f"  {item['status']}: {item['count']}")
        
        # Last sync
        last_sync = stats.get('last_sync')
        if last_sync:
            print(f"\nLast Sync:")
            print(f"  Completed: {last_sync.get('sync_completed_at', 'N/A')}")
            print(f"  Status: {last_sync.get('status', 'N/A')}")
            print(f"  Tickets Fetched: {last_sync.get('tickets_fetched', 0)}")
        else:
            print("\nNo sync history found")
        
        print()
    
    def verify_setup(self) -> None:
        """Verify database setup"""
        print("\n" + "=" * 70)
        print("  VERIFY SETUP")
        print("=" * 70 + "\n")
        
        print("Checking database tables...")
        
        if self.db.verify_setup():
            print("✓ All tables exist\n")
            
            # Show statistics
            stats = self.db.get_statistics()
            print(f"Active API Keys: {stats.get('active_api_keys', 0)}")
            print(f"Total Tickets: {stats.get('total_tickets', 0)}")
            print()
        else:
            print("✗ Setup verification failed")
            print("  Run 'Setup Database' to create tables\n")
    
    def reset_database(self) -> bool:
        """
        Reset database (drop and recreate tables)
        
        Returns:
            True if successful, False otherwise
        """
        print("\n" + "=" * 70)
        print("  RESET DATABASE")
        print("=" * 70 + "\n")
        
        print("⚠️  WARNING: This will DELETE ALL ClickUp data!")
        print("   - All API keys will be removed")
        print("   - All tickets will be deleted")
        print("   - All sync history will be lost")
        print()
        
        confirm = input("Type 'DELETE ALL' to confirm: ").strip()
        
        if confirm != 'DELETE ALL':
            print("Reset cancelled.\n")
            return False
        
        print("\nDropping tables...")
        if not self.db.drop_tables():
            print("✗ Failed to drop tables\n")
            return False
        
        print("Creating tables...")
        if not self.db.create_tables():
            print("✗ Failed to create tables\n")
            return False
        
        print("✓ Database reset complete!\n")
        return True
    
    def main_menu(self) -> None:
        """Display and handle main menu"""
        while True:
            print("\n" + "=" * 70)
            print("  CLICKUP SETUP & MANAGEMENT")
            print("=" * 70 + "\n")
            
            print("Database Setup:")
            print("  1. Setup Database (Create Tables)")
            print("  2. Verify Setup")
            print("  3. Reset Database (DANGER!)")
            print()
            
            print("API Key Management:")
            print("  4. Add API Key")
            print("  5. List API Keys")
            print("  6. Deactivate API Key")
            print("  7. Test API Connections")
            print()
            
            print("Statistics:")
            print("  8. Show Statistics")
            print()
            
            print("  9. Exit")
            print()
            
            choice = input("Enter choice (1-9): ").strip()
            
            if choice == '1':
                self.setup_database()
            
            elif choice == '2':
                self.verify_setup()
            
            elif choice == '3':
                self.reset_database()
            
            elif choice == '4':
                self.add_api_key()
            
            elif choice == '5':
                self.list_api_keys()
            
            elif choice == '6':
                self.deactivate_api_key()
            
            elif choice == '7':
                self.test_api_connection()
            
            elif choice == '8':
                self.show_statistics()
            
            elif choice == '9':
                print("\nGoodbye!\n")
                break
            
            else:
                print("\n✗ Invalid choice. Please try again.\n")


def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("  CLICKUP INTEGRATION SETUP")
    print("=" * 70)
    print()
    print("  This tool helps you set up and manage ClickUp integration")
    print("  for your automation system.")
    print()
    print("=" * 70 + "\n")
    
    try:
        setup = ClickUpSetup()
        setup.main_menu()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...\n")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n✗ Fatal error: {e}\n")


if __name__ == "__main__":
    main()
