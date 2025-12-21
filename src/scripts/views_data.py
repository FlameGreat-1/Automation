"""
ClickUp Views Database Viewer
Shows all stored views in clean table format
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


def format_json_field(json_data, field_name='items'):
    """Format JSON field for display"""
    if not json_data:
        return 'None'
    try:
        data = json.loads(json_data) if isinstance(json_data, str) else json_data
        if isinstance(data, dict):
            return f"{len(data)} {field_name}"
        elif isinstance(data, list):
            return f"{len(data)} {field_name}"
        return 'Present'
    except:
        return 'Invalid JSON'


def view_all_views():
    """Display all stored views"""
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT 
                v.view_id,
                k.key_name,
                v.view_name,
                v.view_type,
                v.workspace_id,
                v.space_id,
                v.list_id,
                v.filters,
                v.grouping,
                v.sorting,
                v.columns,
                v.settings,
                v.creator_username,
                v.is_private,
                v.is_default,
                v.date_created,
                v.date_updated,
                v.created_at
            FROM clickup_views v
            JOIN clickup_api_keys k ON v.api_key_id = k.id
            ORDER BY v.created_at DESC
        """)
        
        views = cursor.fetchall()
        
        if not views:
            print("\nNo views found.\n")
            return
        
        print("\n" + "="*150)
        print(f"CLICKUP CUSTOM VIEWS - TOTAL: {len(views)}")
        print("="*150)
        
        for i, v in enumerate(views, 1):
            print(f"\n[{i}] {v['view_name']}")
            print("-" * 150)
            
            # Basic Info
            print(f"ID: {v['view_id']:<20} Type: {v['view_type']:<15} Private: {'Yes' if v['is_private'] else 'No':<5} Default: {'Yes' if v['is_default'] else 'No'}")
            
            # API Key
            print(f"API Key: {v['key_name']}")
            
            # Hierarchy
            hierarchy_parts = []
            if v['workspace_id']:
                hierarchy_parts.append(f"Workspace: {v['workspace_id']}")
            if v['space_id']:
                hierarchy_parts.append(f"Space: {v['space_id']}")
            if v['list_id']:
                hierarchy_parts.append(f"List: {v['list_id']}")
            
            if hierarchy_parts:
                print(f"Location: {' → '.join(hierarchy_parts)}")
            
            # Configuration Summary
            config_parts = []
            if v['filters']:
                config_parts.append(f"Filters: {format_json_field(v['filters'], 'filters')}")
            if v['grouping']:
                config_parts.append(f"Grouping: {format_json_field(v['grouping'], 'groups')}")
            if v['sorting']:
                config_parts.append(f"Sorting: {format_json_field(v['sorting'], 'sorts')}")
            if v['columns']:
                config_parts.append(f"Columns: {format_json_field(v['columns'], 'columns')}")
            
            if config_parts:
                print(f"Configuration: {' | '.join(config_parts)}")
            
            # Creator
            if v['creator_username']:
                print(f"Creator: {v['creator_username']}")
            
            # Dates
            print(f"Created: {format_timestamp(v['date_created']):<20} Updated: {format_timestamp(v['date_updated']):<20} Stored: {str(v['created_at'])[:19]}")
        
        print("\n" + "="*150 + "\n")


def view_by_type():
    """Display views grouped by type"""
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("""
            SELECT 
                view_type,
                COUNT(*) as count,
                GROUP_CONCAT(view_name SEPARATOR ', ') as view_names
            FROM clickup_views
            GROUP BY view_type
            ORDER BY count DESC
        """)
        
        types = cursor.fetchall()
        
        if not types:
            print("\nNo views found.\n")
            return
        
        print("\n" + "="*100)
        print("VIEWS BY TYPE")
        print("="*100 + "\n")
        
        for t in types:
            print(f"{t['view_type'].upper()}: {t['count']} view(s)")
            names = t['view_names'].split(', ')
            for name in names[:5]:  # Show first 5
                print(f"  • {name}")
            if len(names) > 5:
                print(f"  ... and {len(names) - 5} more")
            print()
        
        print("="*100 + "\n")


def view_statistics():
    """Display view statistics"""
    with get_cursor(dictionary=True) as cursor:
        # Total views
        cursor.execute("SELECT COUNT(*) as total FROM clickup_views")
        total = cursor.fetchone()['total']
        
        # By type
        cursor.execute("""
            SELECT view_type, COUNT(*) as count
            FROM clickup_views
            GROUP BY view_type
            ORDER BY count DESC
        """)
        by_type = cursor.fetchall()
        
        # Private vs Public
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN is_private = 1 THEN 1 ELSE 0 END) as private_count,
                SUM(CASE WHEN is_private = 0 THEN 1 ELSE 0 END) as public_count
            FROM clickup_views
        """)
        privacy = cursor.fetchone()
        
        # Default views
        cursor.execute("SELECT COUNT(*) as count FROM clickup_views WHERE is_default = 1")
        default_count = cursor.fetchone()['count']
        
        print("\n" + "="*100)
        print("VIEW STATISTICS")
        print("="*100 + "\n")
        
        print(f"Total Views: {total}")
        print(f"Private Views: {privacy['private_count']}")
        print(f"Public Views: {privacy['public_count']}")
        print(f"Default Views: {default_count}")
        print()
        
        print("Views by Type:")
        for item in by_type:
            print(f"  {item['view_type']}: {item['count']}")
        
        print("\n" + "="*100 + "\n")


def interactive_menu():
    """Interactive menu"""
    while True:
        print("\n" + "="*100)
        print("CLICKUP VIEWS VIEWER")
        print("="*100 + "\n")
        
        print("1. View All Views (Detailed)")
        print("2. View by Type")
        print("3. View Statistics")
        print("4. Exit")
        print()
        
        choice = input("Enter choice (1-4): ").strip()
        
        if choice == '1':
            view_all_views()
        elif choice == '2':
            view_by_type()
        elif choice == '3':
            view_statistics()
        elif choice == '4':
            print("\nGoodbye!\n")
            break
        else:
            print("\n✗ Invalid choice. Please try again.\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--all':
            view_all_views()
        elif sys.argv[1] == '--type':
            view_by_type()
        elif sys.argv[1] == '--stats':
            view_statistics()
        else:
            print("Usage: python clickup_views_data.py [--all|--type|--stats]")
    else:
        interactive_menu()
