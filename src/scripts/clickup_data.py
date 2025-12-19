"""
ClickUp Database Viewer - UI Relevant Data Only
Shows clean, user-friendly ticket information
"""

import sys
sys.path.insert(0, 'src')

from database.connection import get_cursor
import json
from datetime import datetime


def format_timestamp(ts):
    """Convert timestamp to readable date"""
    if not ts:
        return 'N/A'
    try:
        if isinstance(ts, int):
            return datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d %H:%M')
        return str(ts)[:19]
    except:
        return str(ts)


def format_assignees(assignees_json):
    """Extract usernames from assignees JSON"""
    if not assignees_json:
        return 'None'
    try:
        data = json.loads(assignees_json) if isinstance(assignees_json, str) else assignees_json
        if isinstance(data, list) and data:
            names = [a.get('username', 'Unknown') for a in data]
            return ', '.join(names)
        return 'None'
    except:
        return 'None'


def format_tags(tags_json):
    """Extract tag names from tags JSON"""
    if not tags_json:
        return 'None'
    try:
        data = json.loads(tags_json) if isinstance(tags_json, str) else tags_json
        if isinstance(data, list) and data:
            names = [t.get('name', 'Unknown') for t in data]
            return ', '.join(names)
        return 'None'
    except:
        return 'None'


def view_all_data():
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT 
                t.ticket_id,
                k.key_name,
                t.workspace_name,
                t.list_name,
                t.name,
                t.description,
                t.status,
                t.priority,
                t.due_date,
                t.date_created,
                t.assignees,
                t.creator_username,
                t.tags,
                t.url,
                t.archived
            FROM clickup_tickets t
            JOIN clickup_api_keys k ON t.api_key_id = k.id
            ORDER BY t.date_created DESC
        """)
        
        tickets = cursor.fetchall()
        
        if not tickets:
            print("\nNo tickets found.\n")
            return
        
        print("\n" + "="*150)
        print(f"CLICKUP TICKETS - TOTAL: {len(tickets)}")
        print("="*150)
        
        for i, t in enumerate(tickets, 1):
            print(f"\n[{i}] {t['name']}")
            print("-" * 150)
            
            # Basic Info
            print(f"ID: {t['ticket_id']:<15} Status: {t['status']:<15} Priority: {t['priority']:<10} Archived: {'Yes' if t['archived'] else 'No'}")
            
            # Organization
            print(f"Workspace: {t['workspace_name'] or 'N/A':<30} List: {t['list_name'] or 'N/A'}")
            
            # Description
            desc = t['description'] or 'No description'
            if len(desc) > 120:
                desc = desc[:117] + '...'
            print(f"Description: {desc}")
            
            # People
            print(f"Creator: {t['creator_username'] or 'N/A':<20} Assignees: {format_assignees(t['assignees'])}")
            
            # Tags
            tags = format_tags(t['tags'])
            if tags != 'None':
                print(f"Tags: {tags}")
            
            # Dates
            print(f"Created: {format_timestamp(t['date_created']):<20} Due: {format_timestamp(t['due_date'])}")
            
            # URL
            print(f"URL: {t['url'] or 'N/A'}")
        
        print("\n" + "="*150 + "\n")


if __name__ == "__main__":
    view_all_data()
