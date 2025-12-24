"""
ClickUp Custom Fields Analyzer
Research tool for custom fields structure analysis
"""

import sys
sys.path.insert(0, 'src')

import requests
import json
from typing import Dict, List, Set
from collections import defaultdict
from database.connection import get_cursor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class CustomFieldsAnalyzer:
    """Analyze ClickUp custom fields structure"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.clickup.com/api/v2"
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json"
        }
    
    def get_task_with_custom_fields(self, task_id: str) -> Dict:
        """
        Fetch a specific task with custom fields
        
        Args:
            task_id: ClickUp task ID
            
        Returns:
            Task data with custom fields
        """
        try:
            url = f"{self.base_url}/task/{task_id}"
            params = {
                "include_subtasks": "false",
                "custom_fields": "true"
            }
            
            logger.info(f"Fetching task {task_id}...")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            task = response.json()
            logger.info(f"✓ Task fetched: {task.get('name', 'Unknown')}")
            
            return task
            
        except Exception as e:
            logger.error(f"✗ Error fetching task: {e}")
            return {}
    
    def analyze_custom_fields_structure(self, task: Dict) -> Dict:
        """
        Analyze custom fields to identify common vs type-specific fields
        
        Args:
            task: Task data from ClickUp API
            
        Returns:
            Analysis results
        """
        custom_fields = task.get('custom_fields', [])
        
        if not custom_fields:
            logger.warning("No custom fields found in task")
            return {}
        
        logger.info(f"\nAnalyzing {len(custom_fields)} custom field(s)...")
        
        # Track all fields across all custom field types
        all_fields_by_type = defaultdict(list)
        common_fields = None
        
        analysis = {
            'total_fields': len(custom_fields),
            'field_types': {},
            'common_fields': set(),
            'type_specific_fields': defaultdict(set),
            'raw_samples': []
        }
        
        # Analyze each custom field
        for cf in custom_fields:
            field_type = cf.get('type', 'unknown')
            field_keys = set(cf.keys())
            
            # Track fields for this type
            all_fields_by_type[field_type].append(field_keys)
            
            # Store sample
            analysis['raw_samples'].append({
                'name': cf.get('name'),
                'type': field_type,
                'structure': cf
            })
            
            # Track field type
            if field_type not in analysis['field_types']:
                analysis['field_types'][field_type] = {
                    'count': 0,
                    'sample_name': cf.get('name'),
                    'all_keys': field_keys
                }
            analysis['field_types'][field_type]['count'] += 1
            
            # Find common fields (intersection)
            if common_fields is None:
                common_fields = field_keys.copy()
            else:
                common_fields &= field_keys
        
        # Set common fields
        analysis['common_fields'] = common_fields if common_fields else set()
        
        # Find type-specific fields
        for field_type, keys_list in all_fields_by_type.items():
            all_keys = set()
            for keys in keys_list:
                all_keys |= keys
            
            type_specific = all_keys - analysis['common_fields']
            analysis['type_specific_fields'][field_type] = type_specific
        
        return analysis
    
    def display_analysis(self, analysis: Dict):
        """Display analysis results in readable format"""
        
        print("\n" + "="*100)
        print("CUSTOM FIELDS STRUCTURE ANALYSIS")
        print("="*100 + "\n")
        
        print(f"Total Custom Fields Analyzed: {analysis['total_fields']}\n")
        
        # Field types summary
        print("-" * 100)
        print("FIELD TYPES FOUND:")
        print("-" * 100)
        for field_type, info in analysis['field_types'].items():
            print(f"  • {field_type.upper()}: {info['count']} field(s) - Example: '{info['sample_name']}'")
        
        # Common fields
        print("\n" + "-" * 100)
        print("COMMON FIELDS (Present in ALL custom field types):")
        print("-" * 100)
        if analysis['common_fields']:
            for field in sorted(analysis['common_fields']):
                print(f"  ✓ {field}")
        else:
            print("  ⚠ No common fields found (need more diverse field types)")
        
        # Type-specific fields
        print("\n" + "-" * 100)
        print("TYPE-SPECIFIC FIELDS (Unique to certain types):")
        print("-" * 100)
        for field_type, fields in analysis['type_specific_fields'].items():
            if fields:
                print(f"\n  {field_type.upper()}:")
                for field in sorted(fields):
                    print(f"    • {field}")
        
        # Raw samples
        print("\n" + "="*100)
        print("RAW FIELD SAMPLES:")
        print("="*100 + "\n")
        
        for i, sample in enumerate(analysis['raw_samples'], 1):
            print(f"[{i}] {sample['name']} ({sample['type']})")
            print("-" * 100)
            print(json.dumps(sample['structure'], indent=2))
            print()
        
        print("="*100 + "\n")
    
    def save_analysis(self, analysis: Dict, filename: str = "custom_fields_analysis.json"):
        """Save analysis to JSON file"""
        
        # Convert sets to lists for JSON serialization
        serializable = {
            'total_fields': analysis['total_fields'],
            'field_types': analysis['field_types'],
            'common_fields': sorted(list(analysis['common_fields'])),
            'type_specific_fields': {
                k: sorted(list(v)) for k, v in analysis['type_specific_fields'].items()
            },
            'raw_samples': analysis['raw_samples']
        }
        
        # Convert sets in field_types
        for field_type in serializable['field_types']:
            serializable['field_types'][field_type]['all_keys'] = sorted(
                list(serializable['field_types'][field_type]['all_keys'])
            )
        
        filepath = f"logs/{filename}"
        with open(filepath, 'w') as f:
            json.dump(serializable, f, indent=2)
        
        logger.info(f"✓ Analysis saved to {filepath}")
    
    def generate_table_recommendation(self, analysis: Dict):
        """Generate SQL table structure recommendation"""
        
        print("\n" + "="*100)
        print("RECOMMENDED TABLE STRUCTURE")
        print("="*100 + "\n")
        
        print("Based on analysis, here's the recommended structure:\n")
        
        print("```sql")
        print("CREATE TABLE clickup_custom_fields (")
        print("    id INT AUTO_INCREMENT PRIMARY KEY,")
        print("    ticket_id VARCHAR(50) NOT NULL,")
        print()
        print("    -- COMMON FIELDS (present in all types)")
        
        if analysis['common_fields']:
            for field in sorted(analysis['common_fields']):
                # Suggest data type based on field name
                if field == 'id':
                    print(f"    field_id VARCHAR(50),")
                elif field == 'name':
                    print(f"    field_name VARCHAR(255),")
                elif field == 'type':
                    print(f"    field_type VARCHAR(50),")
                elif field == 'value':
                    print(f"    field_value TEXT,")
                elif 'required' in field:
                    print(f"    is_required BOOLEAN DEFAULT FALSE,")
                else:
                    print(f"    {field} TEXT,")
        else:
            print("    -- No common fields identified")
            print("    -- Add basic fields manually:")
            print("    field_id VARCHAR(50),")
            print("    field_name VARCHAR(255),")
            print("    field_type VARCHAR(50),")
            print("    field_value TEXT,")
        
        print()
        print("    -- TYPE-SPECIFIC FIELDS (stored as JSONB)")
        print("    extra_fields JSONB,")
        print()
        print("    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,")
        print("    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,")
        print()
        print("    FOREIGN KEY (ticket_id) REFERENCES clickup_tickets(ticket_id) ON DELETE CASCADE,")
        print("    INDEX idx_ticket (ticket_id),")
        print("    INDEX idx_field_type (field_type)")
        print(");")
        print("```\n")
        
        print("="*100 + "\n")


def main():
    """Main execution"""
    
    print("\n" + "="*100)
    print("CLICKUP CUSTOM FIELDS RESEARCH TOOL")
    print("="*100 + "\n")
    
    # Get API key from database
    with get_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT api_key FROM clickup_api_keys WHERE is_active = 1 LIMIT 1")
        result = cursor.fetchone()
        
        if not result:
            logger.error("No active API key found in database")
            return
        
        api_key = result['api_key']
    
    # Get task ID from user
    task_id = input("Enter ClickUp Task ID (with custom fields): ").strip()
    
    if not task_id:
        logger.error("Task ID is required")
        return
    
    # Initialize analyzer
    analyzer = CustomFieldsAnalyzer(api_key)
    
    # Fetch task
    task = analyzer.get_task_with_custom_fields(task_id)
    
    if not task:
        return
    
    # Analyze structure
    analysis = analyzer.analyze_custom_fields_structure(task)
    
    if not analysis:
        return
    
    # Display results
    analyzer.display_analysis(analysis)
    
    # Save analysis
    analyzer.save_analysis(analysis)
    
    # Generate table recommendation
    analyzer.generate_table_recommendation(analysis)
    
    logger.info("✓ Analysis complete!")


if __name__ == "__main__":
    main()
