"""
ClickUp Views Fetcher - Enterprise Grade
Fetches and stores custom views from ClickUp API
Production-ready with error handling, logging, and retry logic
"""

import sys
sys.path.insert(0, 'src')

import requests
import json
import time
from typing import List, Dict, Optional
from database.connection import get_cursor
from database.clickup_db import ClickUpDB
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ViewsFetcher:
    """
    Enterprise-grade ClickUp Views Fetcher
    
    Features:
    - Multi-level view fetching (workspace, space, folder, list)
    - Automatic retry on failure
    - Rate limit handling
    - Comprehensive error logging
    - Upsert logic for updates
    """
    
    def __init__(self, api_key: str, api_key_id: int):
        """
        Initialize Views Fetcher
        
        Args:
            api_key: ClickUp API key
            api_key_id: Database ID of the API key
        """
        self.api_key = api_key
        self.api_key_id = api_key_id
        self.base_url = "https://api.clickup.com/api/v2"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
        self.stats = {
            'total_fetched': 0,
            'total_saved': 0,
            'errors': 0
        }
    
    def _make_request(self, url: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Make API request with retry logic
        
        Args:
            url: API endpoint URL
            max_retries: Maximum retry attempts
            
        Returns:
            Response JSON or None on failure
        """
        for attempt in range(1, max_retries + 1):
            try:
                response = requests.get(url, headers=self.headers, timeout=30)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    self.stats['errors'] += 1
                    return None
        
        return None
    
    def fetch_views_by_level(self, level: str, level_id: str) -> List[Dict]:
        """
        Fetch views for a specific level
        
        Args:
            level: 'team', 'space', 'folder', or 'list'
            level_id: ID of the level
            
        Returns:
            List of view dictionaries
        """
        url = f"{self.base_url}/{level}/{level_id}/view"
        data = self._make_request(url)
        
        if data:
            views = data.get('views', [])
            self.stats['total_fetched'] += len(views)
            logger.info(f"✓ Fetched {len(views)} views from {level} {level_id}")
            return views
        
        return []
    
    
    def save_view(self, view: Dict, workspace_id: str = None, 
                  space_id: str = None, folder_id: str = None, 
                  list_id: str = None) -> bool:
        """
        Save view to database with upsert logic
        Auto-detects MySQL 8.0.19+ vs MariaDB and uses appropriate syntax
        
        Args:
            view: View data from ClickUp API
            workspace_id: Workspace ID (optional)
            space_id: Space ID (optional)
            folder_id: Folder ID (optional)
            list_id: List ID (optional)
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Prepare data tuple (used by both queries)
        data = (
            view.get('id'),
            self.api_key_id,
            view.get('name', 'Unnamed View'),
            view.get('type', 'list'),
            workspace_id,
            space_id,
            folder_id,
            list_id,
            json.dumps(view.get('filters', {})),
            json.dumps(view.get('grouping', {})),
            json.dumps(view.get('sorting', {})),
            json.dumps(view.get('columns', [])),
            json.dumps(view.get('settings', {})),
            str(view.get('creator')) if view.get('creator') else None,
            view.get('creator_username'),
            view.get('protected', False),
            view.get('default', False),
            view.get('date_created'),
            view.get('date_updated')
        )
        
        try:
            with get_cursor() as cursor:
                # Try modern MySQL 8.0.19+ syntax first
                query_modern = """
                INSERT INTO clickup_views (
                    view_id, api_key_id, view_name, view_type,
                    workspace_id, space_id, folder_id, list_id,
                    filters, `grouping`, sorting, `columns`, settings,
                    creator_id, creator_username, is_private, is_default,
                    date_created, date_updated
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                ) AS new_values
                ON DUPLICATE KEY UPDATE
                    view_name = new_values.view_name,
                    view_type = new_values.view_type,
                    workspace_id = new_values.workspace_id,
                    space_id = new_values.space_id,
                    folder_id = new_values.folder_id,
                    list_id = new_values.list_id,
                    filters = new_values.filters,
                    `grouping` = new_values.`grouping`,
                    sorting = new_values.sorting,
                    `columns` = new_values.`columns`,
                    settings = new_values.settings,
                    creator_id = new_values.creator_id,
                    creator_username = new_values.creator_username,
                    is_private = new_values.is_private,
                    is_default = new_values.is_default,
                    date_updated = new_values.date_updated,
                    updated_at = CURRENT_TIMESTAMP
                """
                
                try:
                    cursor.execute(query_modern, data)
                    self.stats['total_saved'] += 1
                    return True
                    
                except Exception as e:
                    # Check if it's a syntax error (MariaDB doesn't support AS alias)
                    error_msg = str(e)
                    if '1064' in error_msg or 'syntax' in error_msg.lower():
                        logger.debug(f"Modern syntax not supported, trying legacy syntax...")
                        
                        # Fallback to MariaDB/legacy MySQL syntax
                        query_legacy = """
                        INSERT INTO clickup_views (
                            view_id, api_key_id, view_name, view_type,
                            workspace_id, space_id, folder_id, list_id,
                            filters, `grouping`, sorting, `columns`, settings,
                            creator_id, creator_username, is_private, is_default,
                            date_created, date_updated
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s
                        )
                        ON DUPLICATE KEY UPDATE
                            view_name = VALUES(view_name),
                            view_type = VALUES(view_type),
                            workspace_id = VALUES(workspace_id),
                            space_id = VALUES(space_id),
                            folder_id = VALUES(folder_id),
                            list_id = VALUES(list_id),
                            filters = VALUES(filters),
                            `grouping` = VALUES(`grouping`),
                            sorting = VALUES(sorting),
                            `columns` = VALUES(`columns`),
                            settings = VALUES(settings),
                            creator_id = VALUES(creator_id),
                            creator_username = VALUES(creator_username),
                            is_private = VALUES(is_private),
                            is_default = VALUES(is_default),
                            date_updated = VALUES(date_updated),
                            updated_at = CURRENT_TIMESTAMP
                        """
                        
                        cursor.execute(query_legacy, data)
                        self.stats['total_saved'] += 1
                        return True
                    else:
                        # Different error, re-raise
                        raise
                
        except Exception as e:
            logger.error(f"Error saving view {view.get('name')}: {e}")
            self.stats['errors'] += 1
            return False

    def fetch_all_views(self) -> Dict[str, int]:
        """
        Fetch all views from all hierarchy levels
        
        Returns:
            Statistics dictionary
        """
        logger.info(f"Starting views fetch for API key ID: {self.api_key_id}")
        
        try:
            # Get workspaces/teams
            teams_data = self._make_request(f"{self.base_url}/team")
            if not teams_data:
                logger.error("Failed to fetch teams")
                return self.stats
            
            teams = teams_data.get('teams', [])
            logger.info(f"Found {len(teams)} workspace(s)")
            
            for team in teams:
                team_id = team.get('id')
                team_name = team.get('name')
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing workspace: {team_name}")
                logger.info(f"{'='*60}")
                
                # Workspace-level views
                views = self.fetch_views_by_level('team', team_id)
                for view in views:
                    self.save_view(view, workspace_id=team_id)
                
                # Get spaces
                spaces_data = self._make_request(f"{self.base_url}/team/{team_id}/space")
                if not spaces_data:
                    continue
                
                spaces = spaces_data.get('spaces', [])
                logger.info(f"Found {len(spaces)} space(s) in {team_name}")
                
                for space in spaces:
                    space_id = space.get('id')
                    space_name = space.get('name')
                    
                    # Space-level views
                    views = self.fetch_views_by_level('space', space_id)
                    for view in views:
                        self.save_view(view, workspace_id=team_id, space_id=space_id)
                    
                    # Process folders
                    folders = space.get('folders', [])
                    for folder in folders:
                        folder_id = folder.get('id')
                        
                        # Folder-level views
                        views = self.fetch_views_by_level('folder', folder_id)
                        for view in views:
                            self.save_view(view, workspace_id=team_id, 
                                         space_id=space_id, folder_id=folder_id)
                        
                        # Lists in folder
                        lists = folder.get('lists', [])
                        for lst in lists:
                            list_id = lst.get('id')
                            
                            # List-level views
                            views = self.fetch_views_by_level('list', list_id)
                            for view in views:
                                self.save_view(view, workspace_id=team_id,
                                             space_id=space_id, folder_id=folder_id,
                                             list_id=list_id)
                    
                    # Folderless lists
                    lists = space.get('lists', [])
                    for lst in lists:
                        list_id = lst.get('id')
                        
                        # List-level views
                        views = self.fetch_views_by_level('list', list_id)
                        for view in views:
                            self.save_view(view, workspace_id=team_id,
                                         space_id=space_id, list_id=list_id)
            
            logger.info(f"\n{'='*60}")
            logger.info("Views Fetch Summary:")
            logger.info(f"  Total Fetched: {self.stats['total_fetched']}")
            logger.info(f"  Total Saved: {self.stats['total_saved']}")
            logger.info(f"  Errors: {self.stats['errors']}")
            logger.info(f"{'='*60}\n")
            
        except Exception as e:
            logger.error(f"Fatal error during views fetch: {e}")
            self.stats['errors'] += 1
        
        return self.stats


def main():
    """Main execution function"""
    logger.info("="*60)
    logger.info("ClickUp Views Sync Started")
    logger.info("="*60)
    
    try:
        # Get all API keys
        clickup_db = ClickUpDB()
        api_keys = clickup_db.get_active_api_keys()
        
        if not api_keys:
            logger.warning("No API keys found")
            return
        
        logger.info(f"Found {len(api_keys)} API key(s)\n")
        
        total_stats = {
            'total_fetched': 0,
            'total_saved': 0,
            'errors': 0
        }
        
        # Process each API key
        for api_key_data in api_keys:
            logger.info(f"\nProcessing: {api_key_data['key_name']}")
            
            fetcher = ViewsFetcher(
                api_key_data['api_key'],
                api_key_data['id']
            )
            
            stats = fetcher.fetch_all_views()
            
            # Aggregate stats
            total_stats['total_fetched'] += stats['total_fetched']
            total_stats['total_saved'] += stats['total_saved']
            total_stats['errors'] += stats['errors']
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("FINAL SUMMARY - ALL WORKSPACES")
        logger.info("="*60)
        logger.info(f"Total Views Fetched: {total_stats['total_fetched']}")
        logger.info(f"Total Views Saved: {total_stats['total_saved']}")
        logger.info(f"Total Errors: {total_stats['errors']}")
        logger.info("="*60)
        
        # Exit code based on errors
        if total_stats['errors'] > 0:
            logger.warning("Completed with errors")
            sys.exit(1)
        else:
            logger.info("✓ Completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
