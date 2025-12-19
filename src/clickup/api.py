"""
ClickUp API Client
Wrapper for ClickUp API v2
Handles authentication, rate limiting, retries, and error handling
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class ClickUpAPIError(Exception):
    """Custom exception for ClickUp API errors"""
    pass


class ClickUpRateLimitError(ClickUpAPIError):
    """Raised when rate limit is exceeded"""
    pass


class ClickUpAPI:
    """
    ClickUp API Client with features:
    - Automatic retry with exponential backoff
    - Rate limiting protection
    - Comprehensive error handling
    - Request/response logging
    """
    
    BASE_URL = "https://api.clickup.com/api/v2"
    RATE_LIMIT_REQUESTS = 100  # Per minute
    RATE_LIMIT_WINDOW = 60  # Seconds
    
    def __init__(self, api_token: str):
        """
        Initialize ClickUp API client
        
        Args:
            api_token: ClickUp personal API token (starts with pk_)
        
        Raises:
            ValueError: If api_token is invalid
        """
        if not api_token or not api_token.startswith('pk_'):
            raise ValueError("Invalid ClickUp API token. Must start with 'pk_'")
        
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': api_token,
            'Content-Type': 'application/json'
        })
        
        # Rate limiting tracking
        self._request_times = []
        
        logger.info("✓ ClickUp API client initialized")
    
    def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limiting
        
        Raises:
            ClickUpRateLimitError: If rate limit would be exceeded
        """
        current_time = time.time()
        
        # Remove requests older than rate limit window
        self._request_times = [
            t for t in self._request_times 
            if current_time - t < self.RATE_LIMIT_WINDOW
        ]
        
        # Check if we're at the limit
        if len(self._request_times) >= self.RATE_LIMIT_REQUESTS:
            oldest_request = self._request_times[0]
            wait_time = self.RATE_LIMIT_WINDOW - (current_time - oldest_request)
            
            if wait_time > 0:
                logger.warning(f"⚠ Rate limit reached. Waiting {wait_time:.1f}s")
                time.sleep(wait_time + 1)  # Add 1 second buffer
                self._request_times = []
        
        # Record this request
        self._request_times.append(current_time)
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Make HTTP request to ClickUp API with retry logic
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON body for POST/PUT requests
            max_retries: Maximum number of retry attempts
        
        Returns:
            Dict containing API response
        
        Raises:
            ClickUpAPIError: If request fails after all retries
            ClickUpRateLimitError: If rate limit is exceeded
        """
        url = f"{self.BASE_URL}/{endpoint.lstrip('/')}"
        
        for attempt in range(max_retries):
            try:
                # Check rate limit before making request
                self._check_rate_limit()
                
                # Make request
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                    timeout=30
                )
                
                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"⚠ Rate limited by API. Waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle other errors
                if response.status_code >= 400:
                    error_msg = f"API error {response.status_code}: {response.text}"
                    logger.error(f"✗ {error_msg}")
                    
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.info(f"  Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise ClickUpAPIError(error_msg)
                
                # Success
                logger.debug(f"✓ {method} {endpoint} - Status {response.status_code}")
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.error(f"✗ Request timeout for {endpoint}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ClickUpAPIError(f"Request timeout after {max_retries} attempts")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"✗ Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ClickUpAPIError(f"Request failed: {e}")
        
        raise ClickUpAPIError(f"Failed after {max_retries} attempts")
    
    def get_authorized_teams(self) -> List[Dict[str, Any]]:
        """
        Get all authorized workspaces (teams)
        
        Returns:
            List of workspace dictionaries
        """
        logger.info("Fetching authorized workspaces...")
        response = self._make_request('GET', '/team')
        teams = response.get('teams', [])
        logger.info(f"✓ Found {len(teams)} workspace(s)")
        return teams
    
    def get_spaces(self, team_id: str) -> List[Dict[str, Any]]:
        """
        Get all spaces in a workspace
        
        Args:
            team_id: Workspace ID
        
        Returns:
            List of space dictionaries
        """
        logger.info(f"Fetching spaces for workspace {team_id}...")
        response = self._make_request('GET', f'/team/{team_id}/space')
        spaces = response.get('spaces', [])
        logger.info(f"✓ Found {len(spaces)} space(s)")
        return spaces
    
    def get_lists(self, space_id: str) -> List[Dict[str, Any]]:
        """
        Get all lists in a space
        
        Args:
            space_id: Space ID
        
        Returns:
            List of list dictionaries
        """
        logger.info(f"Fetching lists for space {space_id}...")
        response = self._make_request('GET', f'/space/{space_id}/list')
        lists = response.get('lists', [])
        logger.info(f"✓ Found {len(lists)} list(s)")
        return lists
    
    def get_tasks(
        self, 
        list_id: str, 
        page: int = 0,
        archived: bool = False,
        include_closed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all tasks from a list with pagination
        
        Args:
            list_id: List ID
            page: Page number for pagination (0-indexed)
            archived: Include archived tasks
            include_closed: Include closed/completed tasks
        
        Returns:
            List of task dictionaries
        """
        logger.info(f"Fetching tasks from list {list_id} (page {page})...")
        
        params = {
            'page': page,
            'archived': str(archived).lower(),
            'include_closed': str(include_closed).lower()
        }
        
        response = self._make_request('GET', f'/list/{list_id}/task', params=params)
        tasks = response.get('tasks', [])
        logger.info(f"✓ Found {len(tasks)} task(s) on page {page}")
        return tasks
    
    def get_all_tasks(
        self, 
        list_id: str,
        archived: bool = False,
        include_closed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get ALL tasks from a list (handles pagination automatically)
        
        Args:
            list_id: List ID
            archived: Include archived tasks
            include_closed: Include closed/completed tasks
        
        Returns:
            List of all task dictionaries
        """
        logger.info(f"Fetching ALL tasks from list {list_id}...")
        all_tasks = []
        page = 0
        
        while True:
            tasks = self.get_tasks(
                list_id=list_id,
                page=page,
                archived=archived,
                include_closed=include_closed
            )
            
            if not tasks:
                break
            
            all_tasks.extend(tasks)
            page += 1
            
            # Safety limit to prevent infinite loops
            if page > 100:
                logger.warning("⚠ Reached page limit (100). Stopping pagination.")
                break
        
        logger.info(f"✓ Total tasks fetched: {len(all_tasks)}")
        return all_tasks
    
    def get_task(self, task_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific task
        
        Args:
            task_id: Task ID
        
        Returns:
            Task dictionary with full details
        """
        logger.debug(f"Fetching task {task_id}...")
        response = self._make_request('GET', f'/task/{task_id}')
        return response
    
    def get_all_tasks_from_workspace(
        self, 
        team_id: str,
        archived: bool = False,
        include_closed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get ALL tasks from entire workspace (all spaces and lists)
        
        Args:
            team_id: Workspace ID
            archived: Include archived tasks
            include_closed: Include closed/completed tasks
        
        Returns:
            List of all task dictionaries from workspace
        """
        logger.info(f"Fetching ALL tasks from workspace {team_id}...")
        all_tasks = []
        
        # Get all spaces in workspace
        spaces = self.get_spaces(team_id)
        
        for space in spaces:
            space_id = space['id']
            space_name = space.get('name', 'Unknown')
            logger.info(f"  Processing space: {space_name}")
            
            # Get all lists in space
            lists = self.get_lists(space_id)
            
            for list_item in lists:
                list_id = list_item['id']
                list_name = list_item.get('name', 'Unknown')
                logger.info(f"    Processing list: {list_name}")
                
                # Get all tasks in list
                tasks = self.get_all_tasks(
                    list_id=list_id,
                    archived=archived,
                    include_closed=include_closed
                )
                
                # Add metadata to each task
                for task in tasks:
                    task['_space_id'] = space_id
                    task['_space_name'] = space_name
                    task['_list_id'] = list_id
                    task['_list_name'] = list_name
                
                all_tasks.extend(tasks)
        
        logger.info(f"✓ Total tasks from workspace: {len(all_tasks)}")
        return all_tasks
    
    def test_connection(self) -> bool:
        """
        Test API connection and token validity
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Testing ClickUp API connection...")
            teams = self.get_authorized_teams()
            
            if teams:
                logger.info(f"✓ Connection successful! Found {len(teams)} workspace(s)")
                for team in teams:
                    logger.info(f"  - {team.get('name', 'Unknown')} (ID: {team['id']})")
                return True
            else:
                logger.warning("⚠ Connection successful but no workspaces found")
                return False
                
        except Exception as e:
            logger.error(f"✗ Connection test failed: {e}")
            return False
    
    def get_workspace_summary(self, team_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a workspace
        
        Args:
            team_id: Workspace ID
        
        Returns:
            Dictionary with workspace statistics
        """
        logger.info(f"Generating workspace summary for {team_id}...")
        
        summary = {
            'team_id': team_id,
            'total_spaces': 0,
            'total_lists': 0,
            'total_tasks': 0,
            'spaces': []
        }
        
        spaces = self.get_spaces(team_id)
        summary['total_spaces'] = len(spaces)
        
        for space in spaces:
            space_id = space['id']
            space_name = space.get('name', 'Unknown')
            
            lists = self.get_lists(space_id)
            space_summary = {
                'space_id': space_id,
                'space_name': space_name,
                'total_lists': len(lists),
                'total_tasks': 0
            }
            
            for list_item in lists:
                list_id = list_item['id']
                tasks = self.get_all_tasks(list_id)
                space_summary['total_tasks'] += len(tasks)
            
            summary['total_lists'] += space_summary['total_lists']
            summary['total_tasks'] += space_summary['total_tasks']
            summary['spaces'].append(space_summary)
        
        logger.info(f"✓ Workspace summary complete:")
        logger.info(f"  Spaces: {summary['total_spaces']}")
        logger.info(f"  Lists: {summary['total_lists']}")
        logger.info(f"  Tasks: {summary['total_tasks']}")
        
        return summary


# Convenience function for quick testing
def test_clickup_connection(api_token: str = None) -> bool:
    """
    Quick test of ClickUp API connection
    
    Args:
        api_token: ClickUp API token (optional, reads from env if not provided)
    
    Returns:
        True if connection successful
    """
    if not api_token:
        api_token = os.getenv('CLICKUP_API_TOKEN')
    
    if not api_token:
        logger.error("✗ No API token provided")
        return False
    
    try:
        client = ClickUpAPI(api_token)
        return client.test_connection()
    except Exception as e:
        logger.error(f"✗ Connection test failed: {e}")
        return False


# Module-level test
if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Setup logging for standalone testing
    CURRENT_FILE_DIR = Path(__file__).parent
    AUTOMATION_ROOT = CURRENT_FILE_DIR.parent.parent
    LOG_DIR = AUTOMATION_ROOT / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_DIR / 'clickup_api.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print("\n" + "=" * 70)
    print("  CLICKUP API CLIENT TEST")
    print("=" * 70 + "\n")
    
    # Get API token from environment
    api_token = os.getenv('CLICKUP_API_TOKEN')
    
    if not api_token:
        print("✗ CLICKUP_API_TOKEN not found in .env file")
        print("  Please add: CLICKUP_API_TOKEN=pk_your_token_here")
        sys.exit(1)
    
    try:
        # Initialize client
        client = ClickUpAPI(api_token)
        
        # Test connection
        if client.test_connection():
            print("\n✓ API connection successful!\n")
            
            # Get workspaces
            teams = client.get_authorized_teams()
            
            if teams:
                print(f"Found {len(teams)} workspace(s):\n")
                
                for team in teams:
                    team_id = team['id']
                    team_name = team.get('name', 'Unknown')
                    print(f"Workspace: {team_name} (ID: {team_id})")
                    
                    # Get summary
                    summary = client.get_workspace_summary(team_id)
                    print(f"  Spaces: {summary['total_spaces']}")
                    print(f"  Lists: {summary['total_lists']}")
                    print(f"  Tasks: {summary['total_tasks']}\n")
            
            print("=" * 70)
            print("  ALL TESTS PASSED")
            print("=" * 70 + "\n")
        else:
            print("\n✗ API connection failed\n")
            
    except Exception as e:
        print(f"\n✗ Error during testing: {e}\n")
        sys.exit(1)
