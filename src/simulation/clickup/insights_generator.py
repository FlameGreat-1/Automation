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
from prompts import get_prompt
from config import MAX_TOKENS_INPUT, MAX_TOKENS_OUTPUT, INSIGHTS_OUTPUT_DIR


class InsightsGenerator:
    """Ticket insights generator using LLM"""
    
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
        self.output_dir = Path(INSIGHTS_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _call_llm(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Internal LLM call wrapper"""
        response = self.llm.call_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )
        
        success, content, metadata = self.llm.parse_response(response)
        
        return {
            'success': success,
            'insights': content if success else None,
            'error': content if not success else None,
            'metadata': metadata,
            'timestamp': datetime.now().isoformat(),
            'provider': self.llm.provider,
            'model': self.llm.model
        }
    
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
        
        fitted_tickets, _ = self.structurer.fit_to_token_limit(
            tickets, 
            format_type='json', 
            include_descriptions=False
        )
        
        prompt_parts = []
        prompt_parts.append(f"# Daily Summary for {user_info['username']}")
        prompt_parts.append(f"\n**Date:** {self.now.strftime('%Y-%m-%d')}")
        prompt_parts.append(f"**Total Tickets:** {len(fitted_tickets)}")
        prompt_parts.append(f"**Overdue:** {user_context['overdue_count']}")
        prompt_parts.append(f"**Blocked:** {user_context['blocked_count']}")
        prompt_parts.append(f"**In Progress:** {user_context['in_progress_count']}")
        prompt_parts.append(f"**High Priority:** {user_context['high_priority_count']}")
        
        prompt_parts.append("\n# Tickets\n")
        prompt_parts.append("```json")
        formatted_tickets = [
            self.structurer.format_ticket_json(t, include_description=False) 
            for t in fitted_tickets
        ]
        prompt_parts.append(json.dumps(formatted_tickets, indent=2))
        prompt_parts.append("```")
        
        if include_recommendations:
            prompt_parts.append("\n# Focus Areas:")
            prompt_parts.append("- What are the most critical tasks for today?")
            prompt_parts.append("- Which overdue or blocked tickets need immediate attention?")
            prompt_parts.append("- Are there any potential bottlenecks or risks?")
            prompt_parts.append("- What should be prioritized this week?")
        
        prompt = "\n".join(prompt_parts)
        
        system_prompt = get_prompt(
            'user_daily_summary',
            username=user_info['username'],
            role=user_info['role'],
            department=user_info['department']
        )
        
        response = self._call_llm(prompt, system_prompt, temperature=0.7)
        
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
        
        system_prompt = get_prompt('project_overview', project_name=project_name)
        
        response = self._call_llm(prompt, system_prompt, temperature=0.7)
        
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
        
        context_parts = [
            f"# Critical Tickets Alert",
            f"\n**Total Critical Tickets:** {len(critical_tickets)}",
            f"**Date:** {self.now.strftime('%Y-%m-%d')}",
            "\n---\n"
        ]
        
        context_parts.append(self.structurer.format_tickets_markdown(critical_tickets, include_descriptions=True, add_summary=False))
        
        prompt = "\n".join(context_parts)
        system_prompt = get_prompt('critical_alerts')
        
        response = self._call_llm(prompt, system_prompt, temperature=0.5)
        
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
        system_prompt = get_prompt('team_analysis', department=department)
        
        response = self._call_llm(prompt, system_prompt, temperature=0.7)
        
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
        
        system_prompt = get_prompt('custom_insights')
        
        response = self._call_llm(prompt, system_prompt, temperature=0.7)
        
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
    