"""
ClickUp Ticket Fetcher
Script to fetch tickets from ClickUp API and store in database
Supports multiple API keys and automated daily synchronization
"""

import os
import sys
import logging
import time
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.clickup_db import ClickUpDB
from clickup.api import ClickUpAPI

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
        logging.FileHandler(LOG_DIR / 'clickup_fetcher.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
FETCH_ARCHIVED = os.getenv('CLICKUP_FETCH_ARCHIVED', 'false').lower() == 'true'
FETCH_CLOSED = os.getenv('CLICKUP_FETCH_CLOSED', 'true').lower() == 'true'
DELAY_BETWEEN_KEYS = int(os.getenv('CLICKUP_DELAY_BETWEEN_KEYS', 2))
# =======================================


class ClickUpTicketFetcher:
    """
    ClickUp Ticket Fetcher
    
    Ticket fetching with:
    - Multi-API key support
    - Automatic sync tracking
    - Error recovery
    - Progress reporting
    - Database transaction management
    """
    
    def __init__(self):
        """Initialize ticket fetcher"""
        self.db = ClickUpDB()
        logger.info("ClickUp Ticket Fetcher initialized")
    
    def fetch_tickets_for_key(
        self, 
        api_key_data: Dict[str, Any],
        fetch_archived: bool = FETCH_ARCHIVED,
        fetch_closed: bool = FETCH_CLOSED
    ) -> Tuple[int, int, int]:
        """
        Fetch all tickets for a single API key
        
        Args:
            api_key_data: API key dictionary from database
            fetch_archived: Include archived tickets
            fetch_closed: Include closed tickets
        
        Returns:
            Tuple of (tickets_fetched, tickets_new, tickets_updated)
        """
        api_key_id = api_key_data['id']
        key_name = api_key_data['key_name']
        api_token = api_key_data['api_key']
        workspace_id = api_key_data['workspace_id']
        
        logger.info(f"\n{'=' * 70}")
        logger.info(f"Processing API Key: {key_name}")
        logger.info(f"Workspace ID: {workspace_id or 'Unknown'}")
        logger.info('=' * 70)
        
        # Start sync session
        sync_id = self.db.start_sync(api_key_id)
        if not sync_id:
            logger.error(f"✗ Failed to start sync for {key_name}")
            return (0, 0, 0)
        
        tickets_fetched = 0
        tickets_new = 0
        tickets_updated = 0
        
        try:
            # Initialize API client
            client = ClickUpAPI(api_token)
            
            # Update last used timestamp
            self.db.update_api_key_usage(api_key_id)
            
            # Get all tickets from workspace
            logger.info("Fetching tickets from ClickUp...")
            
            if workspace_id:
                all_tickets = client.get_all_tasks_from_workspace(
                    team_id=workspace_id,
                    archived=fetch_archived,
                    include_closed=fetch_closed
                )
            else:
                # If no workspace_id, get from first available workspace
                teams = client.get_authorized_teams()
                if not teams:
                    logger.warning("⚠ No workspaces found for this API key")
                    self.db.fail_sync(sync_id, "No workspaces found")
                    return (0, 0, 0)
                
                workspace_id = teams[0]['id']
                all_tickets = client.get_all_tasks_from_workspace(
                    team_id=workspace_id,
                    archived=fetch_archived,
                    include_closed=fetch_closed
                )
            
            tickets_fetched = len(all_tickets)
            logger.info(f"✓ Fetched {tickets_fetched} ticket(s) from ClickUp")
            
            if tickets_fetched == 0:
                logger.info("No tickets to process")
                self.db.complete_sync(sync_id, 0, 0, 0)
                return (0, 0, 0)
            
            # Process tickets
            logger.info("Storing tickets in database...")
            
            for idx, ticket in enumerate(all_tickets, 1):
                try:
                    # Check if ticket exists
                    ticket_id = ticket.get('id')
                    existing_tickets = self.db.get_tickets(
                        api_key_id=api_key_id,
                        limit=1
                    )
                    
                    # Determine if new or update
                    is_new = True
                    for existing in existing_tickets:
                        if existing.get('ticket_id') == ticket_id:
                            is_new = False
                            break
                    
                    # Insert/update ticket
                    result = self.db.insert_ticket(
                        api_key_id=api_key_id,
                        ticket_data=ticket
                    )
                    
                    if result:
                        if is_new:
                            tickets_new += 1
                        else:
                            tickets_updated += 1
                        
                        # Progress indicator
                        if idx % 10 == 0 or idx == tickets_fetched:
                            logger.info(f"  Progress: {idx}/{tickets_fetched} tickets processed")
                    
                except Exception as e:
                    logger.error(f"✗ Error processing ticket {ticket.get('id', 'unknown')}: {e}")
                    continue
            
            # Complete sync
            self.db.complete_sync(
                sync_id=sync_id,
                tickets_fetched=tickets_fetched,
                tickets_new=tickets_new,
                tickets_updated=tickets_updated
            )
            
            logger.info(f"\n✓ Sync completed for {key_name}")
            logger.info(f"  Fetched: {tickets_fetched}")
            logger.info(f"  New: {tickets_new}")
            logger.info(f"  Updated: {tickets_updated}")
            
            return (tickets_fetched, tickets_new, tickets_updated)
            
        except Exception as e:
            error_msg = f"Error fetching tickets: {e}"
            logger.error(f"✗ {error_msg}")
            self.db.fail_sync(sync_id, error_msg)
            return (0, 0, 0)
    
    def fetch_all_tickets(
        self,
        fetch_archived: bool = FETCH_ARCHIVED,
        fetch_closed: bool = FETCH_CLOSED
    ) -> Dict[str, Any]:
        """
        Fetch tickets for all active API keys
        
        Args:
            fetch_archived: Include archived tickets
            fetch_closed: Include closed tickets
        
        Returns:
            Dictionary with summary statistics
        """
        logger.info("\n" + "=" * 70)
        logger.info("  CLICKUP TICKET SYNC - STARTING")
        logger.info("=" * 70)
        logger.info(f"Configuration:")
        logger.info(f"  Fetch Archived: {fetch_archived}")
        logger.info(f"  Fetch Closed: {fetch_closed}")
        logger.info(f"  Delay Between Keys: {DELAY_BETWEEN_KEYS}s")
        logger.info("=" * 70 + "\n")
        
        # Get all active API keys
        api_keys = self.db.get_active_api_keys()
        
        if not api_keys:
            logger.warning("⚠ No active API keys found")
            logger.info("  Run setup_clickup.py to add API keys")
            return {
                'total_keys': 0,
                'successful_keys': 0,
                'failed_keys': 0,
                'total_fetched': 0,
                'total_new': 0,
                'total_updated': 0
            }
        
        logger.info(f"Found {len(api_keys)} active API key(s)\n")
        
        # Summary statistics
        summary = {
            'total_keys': len(api_keys),
            'successful_keys': 0,
            'failed_keys': 0,
            'total_fetched': 0,
            'total_new': 0,
            'total_updated': 0,
            'keys_processed': []
        }
        
        # Process each API key
        for idx, api_key_data in enumerate(api_keys, 1):
            key_name = api_key_data['key_name']
            
            logger.info(f"[{idx}/{len(api_keys)}] Processing: {key_name}")
            
            try:
                fetched, new, updated = self.fetch_tickets_for_key(
                    api_key_data=api_key_data,
                    fetch_archived=fetch_archived,
                    fetch_closed=fetch_closed
                )
                
                # Update summary
                if fetched > 0 or (fetched == 0 and new == 0 and updated == 0):
                    summary['successful_keys'] += 1
                else:
                    summary['failed_keys'] += 1
                
                summary['total_fetched'] += fetched
                summary['total_new'] += new
                summary['total_updated'] += updated
                
                summary['keys_processed'].append({
                    'key_name': key_name,
                    'fetched': fetched,
                    'new': new,
                    'updated': updated,
                    'status': 'success' if fetched >= 0 else 'failed'
                })
                
            except Exception as e:
                logger.error(f"✗ Error processing {key_name}: {e}")
                summary['failed_keys'] += 1
                summary['keys_processed'].append({
                    'key_name': key_name,
                    'fetched': 0,
                    'new': 0,
                    'updated': 0,
                    'status': 'failed',
                    'error': str(e)
                })
            
            # Delay between API keys to avoid rate limiting
            if idx < len(api_keys):
                logger.info(f"Waiting {DELAY_BETWEEN_KEYS}s before next key...\n")
                time.sleep(DELAY_BETWEEN_KEYS)
        
        return summary
    
    def print_summary(self, summary: Dict[str, Any]) -> None:
        """
        Print sync summary
        
        Args:
            summary: Summary dictionary from fetch_all_tickets()
        """
        print("\n" + "=" * 70)
        print("  SYNC SUMMARY")
        print("=" * 70 + "\n")
        
        print(f"API Keys Processed: {summary['total_keys']}")
        print(f"  Successful: {summary['successful_keys']}")
        print(f"  Failed: {summary['failed_keys']}")
        print()
        
        print(f"Total Tickets Fetched: {summary['total_fetched']}")
        print(f"  New Tickets: {summary['total_new']}")
        print(f"  Updated Tickets: {summary['total_updated']}")
        print()
        
        # Per-key breakdown
        if summary.get('keys_processed'):
            print("Per-Key Breakdown:")
            for key_info in summary['keys_processed']:
                status_icon = "✓" if key_info['status'] == 'success' else "✗"
                print(f"  {status_icon} {key_info['key_name']}")
                print(f"      Fetched: {key_info['fetched']}, New: {key_info['new']}, Updated: {key_info['updated']}")
                if key_info.get('error'):
                    print(f"      Error: {key_info['error']}")
        
        print("\n" + "=" * 70 + "\n")
    
    def show_database_statistics(self) -> None:
        """Show current database statistics"""
        print("\n" + "=" * 70)
        print("  DATABASE STATISTICS")
        print("=" * 70 + "\n")
        
        stats = self.db.get_statistics()
        
        print(f"Active API Keys: {stats.get('active_api_keys', 0)}")
        print(f"Total Tickets in Database: {stats.get('total_tickets', 0)}")
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
        
        print("\n" + "=" * 70 + "\n")
    
    def run_sync(
        self,
        fetch_archived: bool = FETCH_ARCHIVED,
        fetch_closed: bool = FETCH_CLOSED,
        show_stats: bool = True
    ) -> bool:
        """
        Run complete sync process
        
        Args:
            fetch_archived: Include archived tickets
            fetch_closed: Include closed tickets
            show_stats: Show statistics after sync
        
        Returns:
            True if sync completed successfully, False otherwise
        """
        start_time = time.time()
        
        try:
            # Verify database setup
            if not self.db.verify_setup():
                logger.error("✗ Database not set up properly")
                logger.info("  Run: python database/setup_clickup.py")
                return False
            
            # Fetch tickets
            summary = self.fetch_all_tickets(
                fetch_archived=fetch_archived,
                fetch_closed=fetch_closed
            )
            
            # Print summary
            self.print_summary(summary)
            
            # Show statistics
            if show_stats:
                self.show_database_statistics()
            
            # Calculate duration
            duration = time.time() - start_time
            logger.info(f"✓ Sync completed in {duration:.2f} seconds")
            
            return summary['failed_keys'] == 0
            
        except Exception as e:
            logger.error(f"✗ Sync failed: {e}")
            return False
    
    def interactive_menu(self) -> None:
        """Interactive menu for manual execution"""
        while True:
            print("\n" + "=" * 70)
            print("  CLICKUP TICKET FETCHER")
            print("=" * 70 + "\n")
            
            print("Sync Options:")
            print("  1. Sync All Tickets (Recommended)")
            print("  2. Sync All Tickets (Include Archived)")
            print("  3. Sync All Tickets (Exclude Closed)")
            print()
            
            print("Information:")
            print("  4. Show Database Statistics")
            print("  5. List Active API Keys")
            print()
            
            print("  6. Exit")
            print()
            
            choice = input("Enter choice (1-6): ").strip()
            
            if choice == '1':
                print("\nStarting sync (default settings)...")
                self.run_sync(fetch_archived=False, fetch_closed=True)
            
            elif choice == '2':
                print("\nStarting sync (including archived tickets)...")
                self.run_sync(fetch_archived=True, fetch_closed=True)
            
            elif choice == '3':
                print("\nStarting sync (excluding closed tickets)...")
                self.run_sync(fetch_archived=False, fetch_closed=False)
            
            elif choice == '4':
                self.show_database_statistics()
            
            elif choice == '5':
                self._list_api_keys()
            
            elif choice == '6':
                print("\nGoodbye!\n")
                break
            
            else:
                print("\n✗ Invalid choice. Please try again.\n")
    
    def _list_api_keys(self) -> None:
        """List all active API keys (helper method)"""
        print("\n" + "=" * 70)
        print("  ACTIVE API KEYS")
        print("=" * 70 + "\n")
        
        keys = self.db.get_active_api_keys()
        
        if not keys:
            print("No active API keys found.")
            print("Run: python database/setup_clickup.py to add keys\n")
            return
        
        for idx, key in enumerate(keys, 1):
            print(f"{idx}. {key['key_name']}")
            print(f"   Workspace: {key['workspace_name'] or 'Unknown'}")
            print(f"   Last Sync: {key['last_sync_at'] or 'Never'}")
            print(f"   Total Syncs: {key['total_syncs']}")
            print()


def main():
    """Main execution function"""
    import argparse
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='ClickUp Ticket Fetcher - Sync tickets from ClickUp to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python ClickUp_Ticket_Fetcher.py
  
  # Automated sync (for cronjob)
  python ClickUp_Ticket_Fetcher.py --auto
  
  # Include archived tickets
  python ClickUp_Ticket_Fetcher.py --auto --archived
  
  # Exclude closed tickets
  python ClickUp_Ticket_Fetcher.py --auto --no-closed
        """
    )
    
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Run in automated mode (no interactive menu)'
    )
    
    parser.add_argument(
        '--archived',
        action='store_true',
        help='Include archived tickets'
    )
    
    parser.add_argument(
        '--no-closed',
        action='store_true',
        help='Exclude closed tickets'
    )
    
    parser.add_argument(
        '--no-stats',
        action='store_true',
        help='Skip statistics display'
    )
    
    args = parser.parse_args()
    
    # Banner
    print("\n" + "=" * 70)
    print("  CLICKUP TICKET FETCHER")
    print("=" * 70)
    print()
    print("  Fetches tickets from ClickUp API and stores in local database")
    print()
    print("=" * 70 + "\n")
    
    try:
        fetcher = ClickUpTicketFetcher()
        
        if args.auto:
            # Automated mode (for cronjob)
            logger.info("Running in automated mode")
            
            fetch_archived = args.archived or FETCH_ARCHIVED
            fetch_closed = not args.no_closed
            show_stats = not args.no_stats
            
            success = fetcher.run_sync(
                fetch_archived=fetch_archived,
                fetch_closed=fetch_closed,
                show_stats=show_stats
            )
            
            sys.exit(0 if success else 1)
        
        else:
            # Interactive mode
            fetcher.interactive_menu()
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Exiting...\n")
        sys.exit(130)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"\n✗ Fatal error: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
