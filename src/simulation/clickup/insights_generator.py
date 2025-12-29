class InsightsGenerator:
    """Enterprise-grade ticket insights generator using LLM"""
    
"""
Enterprise-Grade Ticket Insights Generator
Orchestrates filtering, structuring, and LLM calls to generate actionable insights
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

from filter import TicketFilter
from structurer import TicketStructurer
from llm_client import LLMClient
from config import MAX_TOKENS_INPUT, MAX_TOKENS_OUTPUT


class InsightsGenerator:
    """Enterprise-grade ticket insights generator using LLM"""
    
    def __init__(
        self,
        provider: str = 'openai',
        api_key: Optional[str] = None,
        max_tokens: int = MAX_TOKENS_INPUT
    ):
        self.filter = TicketFilter()
        self.structurer = TicketStructurer(max_tokens=max_tokens)
        self.llm = LLMClient(provider=provider, api_key=api_key)
        self.now = datetime.now()
    
    def generate_user_daily_summary(
        self,
        username: str,
        include_recommendations: bool = True
    ) -> Dict[str, Any]:
        """Generate daily summary for a specific user"""
        
        user_context = self.filter.get_user_context(username, include_done=False, days_back=30)
        
        if not user_context or user_context['total_tickets'] == 0:
            return {
                'success': False,
                'error': f'No active tickets found for user: {username}'
            }
        
        user_info = user_context['user']
        tickets = user_context['all_tickets']
        
        prompt = self.structurer.create_insights_prompt(
            tickets=tickets,
            user_info=user_info,
            focus_areas=[
                "What are the most critical tasks for today?",
                "Which overdue or blocked tickets need immediate attention?",
                "Are there any potential bottlenecks or risks?",
                "What should be prioritized this week?"
            ] if include_recommendations else None
        )
        
        system_prompt = f"""You are an AI project management assistant helping {user_info['username']}, 
a {user_info['role']} in the {user_info['department']} department.

Provide a clear, actionable daily summary focusing on:
1. Critical items needing immediate attention
2. Overdue and blocked tickets
3. High-priority work
4. Recommendations for the day

Be concise, specific, and action-oriented."""
        
        response = self.llm.generate_insights(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        if response['success']:
            return {
                'success': True,
                'user': user_info,
                'summary': response['insights'],
                'metadata': {
                    'total_tickets': user_context['total_tickets'],
                    'overdue_count': user_context['overdue_count'],
                    'blocked_count': user_context['blocked_count'],
                    'in_progress_count': user_context['in_progress_count'],
                    'high_priority_count': user_context['high_priority_count'],
                    'generated_at': self.now.isoformat(),
                    'llm_metadata': response.get('metadata', {})
                }
            }
        else:
            return {
                'success': False,
                'error': response.get('error', 'Failed to generate insights')
            }
    
    def generate_project_overview(
        self,
        project_name: str,
        include_team_analysis: bool = True
    ) -> Dict[str, Any]:
        """Generate comprehensive project overview"""
        
        project_context = self.filter.get_project_context(project_name, include_done=False)
        
        if not project_context or project_context['total_tickets'] == 0:
            return {
                'success': False,
                'error': f'No active tickets found for project: {project_name}'
            }
        
        project_info = project_context['project']
        tickets = project_context['all_tickets']
        
        context_parts = [
            f"# Project: {project_name}",
            f"\n**Total Active Tickets:** {project_context['total_tickets']}",
            f"**Overdue:** {project_context['overdue_count']}",
            f"**Blocked:** {project_context['blocked_count']}",
            f"\n**Status Breakdown:**"
        ]
        
        for status, count in project_context['status_breakdown'].items():
            context_parts.append(f"- {status}: {count}")
        
        context_parts.append(f"\n**Type Breakdown:**")
        for ticket_type, count in project_context['type_breakdown'].items():
            context_parts.append(f"- {ticket_type}: {count}")
        
        if include_team_analysis:
            context_parts.append(f"\n**Team Workload:**")
            for assignee, count in sorted(project_context['assignee_breakdown'].items(), key=lambda x: x[1], reverse=True):
                context_parts.append(f"- {assignee}: {count} tickets")
        
        context_parts.append("\n---\n")
        context_parts.append(self.structurer.format_tickets_markdown(tickets[:20], include_descriptions=False, add_summary=False))
        
        prompt = "\n".join(context_parts)
        
        system_prompt = f"""You are an AI project management assistant analyzing the {project_name} project.

Provide a comprehensive project overview including:
1. Overall project health assessment
2. Critical risks and blockers
3. Progress analysis (are we on track?)
4. Team workload balance
5. Recommendations for project success

Be data-driven, specific, and actionable."""
        
        response = self.llm.generate_insights(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        if response['success']:
            return {
                'success': True,
                'project': project_info,
                'overview': response['insights'],
                'metadata': {
                    'total_tickets': project_context['total_tickets'],
                    'status_breakdown': project_context['status_breakdown'],
                    'type_breakdown': project_context['type_breakdown'],
                    'overdue_count': project_context['overdue_count'],
                    'blocked_count': project_context['blocked_count'],
                    'generated_at': self.now.isoformat(),
                    'llm_metadata': response.get('metadata', {})
                }
            }
        else:
            return {
                'success': False,
                'error': response.get('error', 'Failed to generate insights')
            }
    
    def generate_critical_alerts(
        self,
        username: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate alerts for critical tickets"""
        
        critical_tickets = self.filter.get_critical_tickets(username=username)
        
        if not critical_tickets:
            return {
                'success': True,
                'alerts': 'No critical tickets found. All systems normal.',
                'critical_count': 0
            }
        
        user_info = None
        if username:
            user_info = self.filter.get_user_by_username(username)
        
        context_parts = [
            f"# Critical Tickets Alert",
            f"\n**Total Critical Tickets:** {len(critical_tickets)}",
            f"**Date:** {self.now.strftime('%Y-%m-%d')}",
            "\n---\n"
        ]
        
        context_parts.append(self.structurer.format_tickets_markdown(critical_tickets, include_descriptions=True, add_summary=False))
        
        prompt = "\n".join(context_parts)
        
        system_prompt = """You are an AI alert system for critical project issues.

Analyze the critical tickets and provide:
1. Severity assessment (how critical is the situation?)
2. Immediate action items
3. Who should be notified
4. Potential impact if not addressed

Be urgent, clear, and specific about required actions."""
        
        response = self.llm.generate_insights(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.5
        )
        
        if response['success']:
            return {
                'success': True,
                'alerts': response['insights'],
                'critical_count': len(critical_tickets),
                'critical_tickets': [
                    {
                        'id': t['id'],
                        'title': t['name'],
                        'priority': t.get('priority', {}).get('priority', 'none'),
                        'status': t['status']['status'],
                        'assignee': t['assignees'][0]['username'] if t['assignees'] else 'Unassigned'
                    }
                    for t in critical_tickets[:10]
                ],
                'metadata': {
                    'generated_at': self.now.isoformat(),
                    'llm_metadata': response.get('metadata', {})
                }
            }
        else:
            return {
                'success': False,
                'error': response.get('error', 'Failed to generate alerts')
            }
    
    def generate_team_analysis(
        self,
        department: str
    ) -> Dict[str, Any]:
        """Generate team/department workload analysis"""
        
        team_context = self.filter.get_team_context(department, include_done=False)
        
        if not team_context or team_context['total_tickets'] == 0:
            return {
                'success': False,
                'error': f'No active tickets found for department: {department}'
            }
        
        context_parts = [
            f"# {department} Department Analysis",
            f"\n**Team Size:** {team_context['team_size']} members",
            f"**Total Active Tickets:** {team_context['total_tickets']}",
            f"\n**Workload Distribution:**"
        ]
        
        for username, workload in sorted(team_context['user_workload'].items(), key=lambda x: x[1]['total'], reverse=True):
            context_parts.append(
                f"- {username}: {workload['total']} tickets "
                f"(Overdue: {workload['overdue']}, Blocked: {workload['blocked']})"
            )
        
        context_parts.append("\n---\n")
        
        tickets = team_context['all_tickets'][:30]
        context_parts.append(self.structurer.format_tickets_markdown(tickets, include_descriptions=False, add_summary=False))
        
        prompt = "\n".join(context_parts)
        
        system_prompt = f"""You are an AI team management assistant analyzing the {department} department.

Provide a comprehensive team analysis including:
1. Workload balance assessment (is work distributed fairly?)
2. Team bottlenecks and capacity issues
3. Members who may be overloaded or underutilized
4. Collaboration opportunities
5. Recommendations for improving team efficiency

Be specific about team dynamics and actionable improvements."""
        
        response = self.llm.generate_insights(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        if response['success']:
            return {
                'success': True,
                'department': department,
                'analysis': response['insights'],
                'metadata': {
                    'team_size': team_context['team_size'],
                    'total_tickets': team_context['total_tickets'],
                    'user_workload': team_context['user_workload'],
                    'generated_at': self.now.isoformat(),
                    'llm_metadata': response.get('metadata', {})
                }
            }
        else:
            return {
                'success': False,
                'error': response.get('error', 'Failed to generate team analysis')
            }
    
    def generate_custom_insights(
        self,
        tickets: List[Dict[str, Any]],
        question: str,
        context_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate custom insights based on specific question"""
        
        if not tickets:
            return {
                'success': False,
                'error': 'No tickets provided for analysis'
            }
        
        additional_context = None
        if context_info:
            context_parts = []
            for key, value in context_info.items():
                context_parts.append(f"{key}: {value}")
            additional_context = "\n".join(context_parts)
        
        prompt = self.structurer.create_prompt_context(
            tickets=tickets,
            question=question,
            user_info=context_info.get('user') if context_info else None,
            additional_context=additional_context
        )
        
        system_prompt = """You are an expert AI project management assistant.
Analyze the provided ticket data and answer the question with specific, actionable insights.
Use data from the tickets to support your analysis."""
        
        response = self.llm.generate_insights(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7
        )
        
        if response['success']:
            return {
                'success': True,
                'question': question,
                'answer': response['insights'],
                'metadata': {
                    'tickets_analyzed': len(tickets),
                    'generated_at': self.now.isoformat(),
                    'llm_metadata': response.get('metadata', {})
                }
            }
        else:
            return {
                'success': False,
                'error': response.get('error', 'Failed to generate insights')
            }
    
    def format_insights_markdown(self, insights: Dict[str, Any]) -> str:
        """Format insights as readable Markdown"""
        
        if not insights.get('success'):
            return f"# Error\n\n{insights.get('error', 'Unknown error')}"
        
        lines = []
        
        if 'user' in insights:
            user = insights['user']
            lines.append(f"# Daily Summary for {user['username']}")
            lines.append(f"**Role:** {user['role']} | **Department:** {user['department']}")
            lines.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
            lines.append("\n---\n")
            
            if 'metadata' in insights:
                meta = insights['metadata']
                lines.append("## Quick Stats")
                lines.append(f"- Total Active Tickets: {meta.get('total_tickets', 0)}")
                lines.append(f"- Overdue: {meta.get('overdue_count', 0)}")
                lines.append(f"- Blocked: {meta.get('blocked_count', 0)}")
                lines.append(f"- In Progress: {meta.get('in_progress_count', 0)}")
                lines.append(f"- High Priority: {meta.get('high_priority_count', 0)}")
                lines.append("\n---\n")
            
            lines.append("## Insights\n")
            lines.append(insights.get('summary', ''))
        
        elif 'project' in insights:
            project = insights['project']
            lines.append(f"# Project Overview: {project['list_name']}")
            lines.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
            lines.append("\n---\n")
            
            if 'metadata' in insights:
                meta = insights['metadata']
                lines.append("## Project Stats")
                lines.append(f"- Total Active Tickets: {meta.get('total_tickets', 0)}")
                lines.append(f"- Overdue: {meta.get('overdue_count', 0)}")
                lines.append(f"- Blocked: {meta.get('blocked_count', 0)}")
                
                if 'status_breakdown' in meta:
                    lines.append("\n**Status Distribution:**")
                    for status, count in meta['status_breakdown'].items():
                        lines.append(f"- {status}: {count}")
                
                lines.append("\n---\n")
            
            lines.append("## Analysis\n")
            lines.append(insights.get('overview', ''))
        
        elif 'department' in insights:
            lines.append(f"# Team Analysis: {insights['department']} Department")
            lines.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
            lines.append("\n---\n")
            
            if 'metadata' in insights:
                meta = insights['metadata']
                lines.append("## Team Stats")
                lines.append(f"- Team Size: {meta.get('team_size', 0)}")
                lines.append(f"- Total Tickets: {meta.get('total_tickets', 0)}")
                lines.append("\n---\n")
            
            lines.append("## Analysis\n")
            lines.append(insights.get('analysis', ''))
        
        elif 'alerts' in insights:
            lines.append("# Critical Alerts")
            lines.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
            lines.append(f"**Critical Tickets:** {insights.get('critical_count', 0)}")
            lines.append("\n---\n")
            lines.append(insights.get('alerts', ''))
        
        elif 'question' in insights:
            lines.append(f"# Custom Analysis")
            lines.append(f"**Question:** {insights['question']}")
            lines.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
            lines.append("\n---\n")
            lines.append(insights.get('answer', ''))
        
        return "\n".join(lines)
    
    def export_insights(
        self,
        insights: Dict[str, Any],
        filename: Optional[str] = None,
        format_type: str = 'markdown'
    ) -> bool:
        """Export insights to file"""
        
        if not filename:
            timestamp = self.now.strftime('%Y%m%d_%H%M%S')
            if 'user' in insights:
                filename = f"insights_user_{insights['user']['username']}_{timestamp}"
            elif 'project' in insights:
                filename = f"insights_project_{insights['project']['list_name']}_{timestamp}"
            elif 'department' in insights:
                filename = f"insights_team_{insights['department']}_{timestamp}"
            else:
                filename = f"insights_{timestamp}"
        
        output_dir = Path(__file__).parent / "datasets" / "insights"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if format_type == 'markdown':
                filepath = output_dir / f"{filename}.md"
                content = self.format_insights_markdown(insights)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                filepath = output_dir / f"{filename}.json"
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(insights, f, indent=2, ensure_ascii=False)
            
            print(f"✓ Insights exported to {filepath.name}")
            return True
        
        except Exception as e:
            print(f"✗ Error exporting insights: {e}")
            return False
    
    def batch_generate_user_summaries(
        self,
        usernames: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Generate daily summaries for multiple users"""
        
        if not usernames:
            usernames = [u['username'] for u in self.filter.users]
        
        results = {}
        
        print(f"\nGenerating summaries for {len(usernames)} users...")
        
        for i, username in enumerate(usernames, 1):
            print(f"[{i}/{len(usernames)}] Processing {username}...")
            
            result = self.generate_user_daily_summary(username)
            results[username] = result
            
            if result['success']:
                print(f"  ✓ Summary generated")
            else:
                print(f"  ✗ {result.get('error', 'Failed')}")
        
        return results


if __name__ == "__main__":
    from filter import TicketFilter
    
    print("\n" + "="*70)
    print("INSIGHTS GENERATOR - DEMO")
    print("="*70)
    
    try:
        generator = InsightsGenerator()
        filter_system = TicketFilter()
        
        print("\n[1] Testing LLM connection...")
        success, message = generator.llm.test_connection()
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ {message}")
            print("\nPlease configure LLM_API_KEY in .env file")
            exit(1)
        
        print("\n[2] Generating user daily summary...") 
        first_user = filter_system.users[0]['username']
        user_summary = generator.generate_user_daily_summary(first_user)
        
        if user_summary['success']:
            print(f"  ✓ Summary generated for {user_summary['user']['username']}")
            print(f"  Tickets analyzed: {user_summary['metadata']['total_tickets']}")
            print(f"\n  Preview:")
            print(f"  {user_summary['summary'][:200]}...")
            
            generator.export_insights(user_summary, format_type='markdown')
        else:
            print(f"  ✗ {user_summary.get('error')}")
        
        print("\n[3] Generating project overview...")
        project_overview = generator.generate_project_overview("Platform")
        
        if project_overview['success']:
            print(f"  ✓ Overview generated for {project_overview['project']['list_name']}")
            print(f"  Tickets analyzed: {project_overview['metadata']['total_tickets']}")
            
            generator.export_insights(project_overview, format_type='markdown')
        else:
            print(f"  ✗ {project_overview.get('error')}")
        
        print("\n[4] Generating critical alerts...")
        alerts = generator.generate_critical_alerts()
        
        if alerts['success']:
            print(f"  ✓ Alerts generated")
            print(f"  Critical tickets: {alerts['critical_count']}")
            
            if alerts['critical_count'] > 0:
                generator.export_insights(alerts, format_type='markdown')
        else:
            print(f"  ✗ {alerts.get('error')}")
        
        print("\n" + "="*70)
        print("✓ Demo complete! Check src/simulation/clickup/datasets/insights/")
        print("="*70)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
