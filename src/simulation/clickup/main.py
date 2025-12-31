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
        
        print(f"\n✓ Saved to: {filepath}")
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
            else:
                print("\n✗ Invalid choice. Please try again.")
                input("\nPress Enter to continue...")


if __name__ == "__main__":
    app = TicketIntelligenceSystem()
    app.run()
