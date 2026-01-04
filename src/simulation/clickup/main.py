#!/usr/bin/env python3
"""
ClickUp Ticket Intelligence System - Main Interface
Clean, interactive menu for non-technical users
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import time
import re

sys.path.insert(0, str(Path(__file__).parent / 'src' / 'simulation' / 'clickup'))

from filter import TicketFilter
from structurer import TicketStructurer
from llm_client import LLMClient
from insights_generator import InsightsGenerator
from config import INSIGHTS_OUTPUT_DIR


class TicketIntelligenceSystem:
    """Main system controller with interactive menu"""
    
    def __init__(self):
        self.filter_system = None
        self.structurer = None
        self.llm_client = None
        self.insights_generator = None
        self.insights_dir = INSIGHTS_OUTPUT_DIR
        
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """Print system header"""
        print("\n" + "="*70)
        print("     CLICKUP TICKET INTELLIGENCE SYSTEM")
        print("="*70 + "\n")
    
    def print_menu(self):
        """Print main menu"""
        print("MANAGEMENT:")
        print("  1. Generate data")
        print("  2. Preprocess")
        print("  3. All (Run 1-2)")
        print()
        print("INSIGHTS:")
        print("  4. Daily summary (specific user)")
        print("  5. Daily summary (all users)")
        print("  6. Project overview (specific project)")
        print("  7. Overviews for ALL projects")
        print("  8. Critical alerts (workspace-wide)")
        print("  9. Workspace analysis")
        print("  10. Feature analysis (2-step AI evaluation)")
        print()
        print("  0. Exit")
        print()
    
    def stream_and_save(self, content: str, filename: str):
        """Stream content to terminal and save to markdown file"""
        print("\n" + "="*70)
        print("STREAMING INSIGHTS:")
        print("="*70 + "\n")
        
        clean_content = content
        clean_content = re.sub(r'^#{1,6}\s+', '', clean_content, flags=re.MULTILINE)
        clean_content = re.sub(r'\*\*(.+?)\*\*', r'\1', clean_content)
        clean_content = re.sub(r'__(.+?)__', r'\1', clean_content)
        clean_content = re.sub(r'\*(.+?)\*', r'\1', clean_content)
        clean_content = re.sub(r'_(.+?)_', r'\1', clean_content)
        clean_content = re.sub(r'`(.+?)`', r'\1', clean_content)
        clean_content = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean_content)
        
        for char in clean_content:
            print(char, end='', flush=True)
            time.sleep(0.001)
        
        print("\n" + "="*70)
        
        self.insights_dir.mkdir(parents=True, exist_ok=True)
        filepath = self.insights_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Saved: insights/{filename}")
        print("="*70 + "\n")
    
    def run_generate_data(self):
        """Option 1: Generate sample data"""
        print("\n[1] Generating sample data...")
        os.system('python src/simulation/clickup/data_generator.py')
        input("\nPress Enter to continue...")
    
    def run_preprocess(self):
        """Option 2: Run preprocessing"""
        print("\n[2] Running preprocessing...")
        os.system('python src/simulation/clickup/preprocessor.py')
        input("\nPress Enter to continue...")
    
    def run_all_management(self):
        """Option 3: Run all management tasks"""
        print("\n[3] Running all management tasks...\n")
        self.run_generate_data()
        self.run_preprocess()
        print("\n✓ All management tasks complete!")
        input("\nPress Enter to continue...")
    
    def initialize_insights_system(self):
        """Initialize insights generator if not already done"""
        if self.insights_generator is None:
            print("\nInitializing system...")
            try:
                self.insights_generator = InsightsGenerator()
                self.filter_system = TicketFilter()
                print("✓ System initialized\n")  
                return True
            except Exception as e:
                print(f"✗ Error initializing system: {e}")
                print("\nMake sure you have:")
                print("  1. Generated data (Option 1)")
                print("  2. Set LLM_API_KEY in .env file")
                input("\nPress Enter to continue...")
                return False
        return True  

    def run_user_summary(self):
        """Option 4: Daily summary for specific user"""
        if not self.initialize_insights_system():
            return
        
        print("\n[4] Daily Summary - Specific User\n")
        
        print("Available users:")
        for i, user in enumerate(self.filter_system.users[:10], 1):
            user_tickets = self.filter_system.filter_by_assignee(user['username'])
            print(f"  {i}. {user['username']} ({user['role']}) - {len(user_tickets)} tickets")
        
        if len(self.filter_system.users) > 10:
            print(f"  ... and {len(self.filter_system.users) - 10} more")
        
        user_input = input("\nEnter username or number (or press Enter for first user): ").strip()
        
        if not user_input:
            username = self.filter_system.users[0]['username']
        elif user_input.isdigit():
            user_index = int(user_input) - 1
            if 0 <= user_index < len(self.filter_system.users):
                username = self.filter_system.users[user_index]['username']
            else:
                print(f"\n✗ Invalid number. Please enter 1-{len(self.filter_system.users)}")
                input("\nPress Enter to continue...")
                return
        else:
            username = user_input
        
        print(f"\nGenerating summary for {username}...")
        
        try:
            result = self.insights_generator.generate_user_daily_summary(username)
            
            if result['success']:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"insights_user_{username}_{timestamp}.md"
                self.stream_and_save(result['summary'], filename)
            else:
                print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"\n✗ Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def run_all_users_summary(self):
        """Option 5: Daily summary for all users"""
        if not self.initialize_insights_system():
            return
        
        print("\n[5] Daily Summary - All Users\n")
        
        total_users = len(self.filter_system.users)
        print(f"Processing {total_users} users...\n")
        
        successful = 0
        skipped = 0
        
        for i, user in enumerate(self.filter_system.users, 1):
            username = user['username']
            print(f"[{i}/{total_users}] {username}...\n")
            
            try:
                result = self.insights_generator.generate_user_daily_summary(username)
                
                if result['success'] and result['metadata']['total_tickets'] > 0:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"insights_user_{username}_{timestamp}.md"
                    self.stream_and_save(result['summary'], filename)
                    print(f"  ✓ {username} saved ({result['metadata']['total_tickets']} tickets)\n")
                    successful += 1
                else:
                    print(f"  ⊘ {username} - no active tickets\n")
                    skipped += 1
            
            except Exception as e:
                print(f"  ✗ Error: {e}\n")
                skipped += 1
        
        print(f"✓ Complete! Generated {successful} insights, skipped {skipped}")
        input("\nPress Enter to continue...")
    
    def run_project_overview(self):
        """Option 6: Project overview for specific project"""
        if not self.initialize_insights_system():
            return
        
        print("\n[6] Project Overview - Specific Project\n")
        
        projects = list(set([t['_list_name'] for t in self.filter_system.tickets]))
        
        print("Available projects:")
        for i, project in enumerate(projects[:10], 1):
            project_tickets = self.filter_system.filter_by_project(project)
            print(f"  {i}. {project} ({len(project_tickets)} tickets)")
        
        if len(projects) > 10:
            print(f"  ... and {len(projects) - 10} more")
        
        project_input = input("\nEnter project name or number (or press Enter for first): ").strip()
        
        if not project_input:
            project_name = projects[0]
        elif project_input.isdigit():
            project_index = int(project_input) - 1
            if 0 <= project_index < len(projects):
                project_name = projects[project_index]
            else:
                print(f"\n✗ Invalid number. Please enter 1-{len(projects)}")
                input("\nPress Enter to continue...")
                return
        else:
            project_name = project_input
        
        print(f"\nGenerating overview for {project_name}...")
        
        try:
            result = self.insights_generator.generate_project_overview(project_name)
            
            if result['success']:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"insights_project_{project_name.replace(' ', '_')}_{timestamp}.md"
                self.stream_and_save(result['overview'], filename)
            else:
                print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"\n✗ Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def run_all_projects_overview(self):
        """Option 7: Overviews for all projects"""
        if not self.initialize_insights_system():
            return
        
        print("\n[7] Project Overviews - All Projects\n")
        
        projects = list(set([t['_list_name'] for t in self.filter_system.tickets]))
        print(f"Processing {len(projects)} projects...\n")
        
        successful = 0
        
        for i, project_name in enumerate(projects, 1):
            print(f"[{i}/{len(projects)}] {project_name}...\n")
            
            try:
                result = self.insights_generator.generate_project_overview(project_name)
                
                if result['success']:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"insights_project_{project_name.replace(' ', '_')}_{timestamp}.md"
                    self.stream_and_save(result['overview'], filename)
                    print(f"  ✓ {project_name} saved ({result['metadata']['total_tickets']} tickets)\n")
                    successful += 1
                else:
                    print(f"  ✗ Failed to generate overview\n")
            
            except Exception as e:
                print(f"  ✗ Error: {e}\n")
        
        print(f"✓ Complete! Generated {successful} overviews")
        input("\nPress Enter to continue...")
    
    def run_critical_alerts(self):
        """Option 8: Critical alerts workspace-wide"""
        if not self.initialize_insights_system():
            return
        
        print("\n[8] Critical Alerts - Workspace Wide\n")
        print("Generating critical alerts...")
        
        try:
            result = self.insights_generator.generate_critical_alerts()
            
            if result['success']:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"insights_critical_alerts_{timestamp}.md"
                self.stream_and_save(result['alerts'], filename)
            else:
                print(f"\n✗ Error: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"\n✗ Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def run_workspace_analysis(self):
        """Option 9: Complete workspace analysis"""
        if not self.initialize_insights_system():
            return
        
        print("\n[9] Complete Workspace Analysis\n")
        print("Generating workspace analysis...\n")
        
        projects = list(set([t['_list_name'] for t in self.filter_system.tickets]))
        
        print("[1/2] Generating critical alerts...\n")
        try:
            result = self.insights_generator.generate_critical_alerts()
            if result['success']:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"insights_critical_alerts_{timestamp}.md"
                self.stream_and_save(result['alerts'], filename)
                print(f"  ✓ Critical alerts saved\n")
        except Exception as e:
            print(f"  ✗ Error: {e}\n")
        
        print("[2/2] Generating project overviews...\n")
        successful = 0
        for i, project_name in enumerate(projects, 1):
            print(f"  [{i}/{len(projects)}] {project_name}...\n")
            
            try:
                result = self.insights_generator.generate_project_overview(project_name)
                
                if result['success']:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"insights_project_{project_name.replace(' ', '_')}_{timestamp}.md"
                    self.stream_and_save(result['overview'], filename)
                    print(f"  ✓ {project_name} saved\n")
                    successful += 1
                else:
                    print(f"  ✗ Failed\n")
            except Exception as e:
                print(f"  ✗ Error: {e}\n")
        
        print(f"✓ Workspace analysis complete! Generated {successful + 1} insights")
        input("\nPress Enter to continue...")
    
    def run_feature_analysis(self):
        """Option 10: Feature Development Analysis (2-step AI evaluation)"""
        if not self.initialize_insights_system():
            return
        
        print("\n[10] Feature Development Analysis (2-Step AI Evaluation)\n")
        
        print("This analysis will:")
        print("  1. Find all tickets related to your feature across the workspace")
        print("  2. Analyze the current development approach")
        print("  3. Evaluate against industry best practices")
        print("  4. Provide expert recommendations\n")
        
        feature_name = input("Enter feature name (e.g., Invoice, Authentication, Dashboard): ").strip()
        
        if not feature_name:
            print("\n✗ Feature name cannot be empty")
            input("\nPress Enter to continue...")
            return
        
        print("\nUse AI-powered smart filtering?")
        print("  - YES: More accurate, finds semantically related tickets (slower, uses more tokens)")
        print("  - NO:  Faster, keyword-only search")
        
        use_smart = input("\nUse smart filtering? (y/n, default=y): ").strip().lower()
        use_smart_filter = use_smart != 'n'
        
        include_done_input = input("Include completed tickets? (y/n, default=n): ").strip().lower()
        include_done = include_done_input == 'y'
        
        print(f"\n{'='*70}")
        print(f"ANALYZING FEATURE: {feature_name}")
        print(f"{'='*70}\n")
        
        if use_smart_filter:
            print("⚙️  Smart filtering: ENABLED")
        else:
            print("⚙️  Smart filtering: DISABLED (keyword search only)")
        
        if include_done:
            print("⚙️  Including: ALL tickets (including completed)")
        else:
            print("⚙️  Including: ACTIVE tickets only")
        
        print()
        
        try:
            result = self.insights_generator.analyze_feature_development(
                feature_name=feature_name,
                use_smart_filter=use_smart_filter,
                include_done=include_done,
                save_outputs=False  
            )
            
            if not result['success']:
                print(f"\n✗ Analysis failed: {result.get('error', 'Unknown error')}")
                input("\nPress Enter to continue...")
                return
            
            print(f"\n{'='*70}")
            print("ANALYSIS COMPLETE")
            print(f"{'='*70}\n")
            print(f"✓ Tickets analyzed: {result['tickets_found']}")
            print(f"✓ Projects involved: {result['metadata']['projects_involved']}")
            print(f"✓ Team members involved: {result['metadata']['team_members_involved']}")
            
            if result['metadata']['overdue_count'] > 0:
                print(f"⚠️  Overdue tickets: {result['metadata']['overdue_count']}")
            
            if result['metadata']['blocked_count'] > 0:
                print(f"🚫 Blocked tickets: {result['metadata']['blocked_count']}")
            
            print()
            
            print(f"{'='*70}")
            print("PART 1: CURRENT DEVELOPMENT APPROACH")
            print(f"{'='*70}\n")
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            current_filename = f"feature_{feature_name.replace(' ', '_')}_current_{timestamp}.md"
            
            current_analysis_with_header = f"""# Current Development Approach: {feature_name}

**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Tickets Analyzed:** {result['tickets_found']}
**Projects Involved:** {result['metadata']['projects_involved']}
**Team Members Involved:** {result['metadata']['team_members_involved']}

---

{result['current_analysis']}
"""
            
            self.stream_and_save(current_analysis_with_header, current_filename)
            
            print(f"\n{'='*70}")
            print("PART 2: BEST PRACTICE EVALUATION & RECOMMENDATIONS")
            print(f"{'='*70}\n")
            
            best_practice_filename = f"feature_{feature_name.replace(' ', '_')}_best_practice_{timestamp}.md"
            
            best_practice_with_header = f"""# Best Practice Evaluation: {feature_name}

**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Tickets Analyzed:** {result['tickets_found']}

---

{result['best_practice_evaluation']}
"""
            
            self.stream_and_save(best_practice_with_header, best_practice_filename)
            
            print(f"\n{'='*70}")
            print("✓ FEATURE ANALYSIS COMPLETE")
            print(f"{'='*70}\n")
            print(f"Feature: {feature_name}")
            print(f"Tickets analyzed: {result['tickets_found']}")
            print(f"Files saved: 2")
            print(f"  - {current_filename}")
            print(f"  - {best_practice_filename}")
            print()
            
            print("Analysis Details:")
            print(f"  Smart Filtering: {'Yes' if result['metadata']['used_smart_filter'] else 'No'}")
            
            if use_smart_filter:
                print(f"  Keyword Matches: {result['metadata']['keyword_matches']}")
                print(f"  Validated Matches: {result['metadata']['validated_matches']}")
            
            print()
        
        except KeyboardInterrupt:
            print("\n\n✗ Analysis cancelled by user")
        
        except Exception as e:
            print(f"\n✗ Unexpected error: {e}")
            print("\nPlease check:")
            print("  1. Your LLM API key is valid")
            print("  2. You have internet connection")
            print("  3. The feature name is correct")
        
        input("\nPress Enter to continue...")
    
    def run(self):
        """Main application loop"""
        while True:
            self.clear_screen()
            self.print_header()
            self.print_menu()
            
            choice = input("Enter your choice: ").strip()
            
            if choice == '0':
                print("\nGoodbye!")
                break
            elif choice == '1':
                self.run_generate_data()
            elif choice == '2':
                self.run_preprocess()
            elif choice == '3':
                self.run_all_management()
            elif choice == '4':
                self.run_user_summary()
            elif choice == '5':
                self.run_all_users_summary()
            elif choice == '6':
                self.run_project_overview()
            elif choice == '7':
                self.run_all_projects_overview()
            elif choice == '8':
                self.run_critical_alerts()
            elif choice == '9':
                self.run_workspace_analysis()
            elif choice == '10':
                self.run_feature_analysis()
            else:
                print("\n✗ Invalid choice. Please try again.")
                input("\nPress Enter to continue...")


if __name__ == "__main__":
    app = TicketIntelligenceSystem()
    app.run()
