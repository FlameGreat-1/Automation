"""
Ticket Insights Generator
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
from config import MAX_TOKENS_INPUT, MAX_TOKENS_OUTPUT, INSIGHTS_OUTPUT_DIR, BEST_PRACTICES_PATH


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
        self.best_practices_content = self._load_best_practices()
    
    def _load_best_practices(self) -> Optional[str]:
        """Load best practices document from file"""
        try:
            best_practices_path = Path(BEST_PRACTICES_PATH)
            
            if not best_practices_path.exists():
                print(f"⚠ Warning: Best practices file not found at {BEST_PRACTICES_PATH}")
                print(f"  Best practice evaluation will proceed without the reference document.\n")
                return None
            
            with open(best_practices_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"✓ Loaded best practices document ({len(content)} characters)\n")
            return content
            
        except Exception as e:
            print(f"⚠ Warning: Failed to load best practices document: {e}")
            print(f"  Best practice evaluation will proceed without the reference document.\n")
            return None
    
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

    def analyze_feature_development(
        self,
        feature_name: str,
        use_smart_filter: bool = True,
        include_done: bool = False,
        save_outputs: bool = True
    ) -> Dict[str, Any]:
        """
        Two-step AI-powered feature development analysis
        
        Step 1: Analyzes tickets to discover current development approach
        Step 2: Evaluates approach against best practices and recommends improvements
        
        Args:
            feature_name: Name of the feature to analyze (e.g., "Invoice", "Authentication")
            use_smart_filter: Whether to use LLM validation for ticket filtering
            include_done: Whether to include completed tickets in analysis
            save_outputs: Whether to save analysis outputs to files
        
        Returns:
            Dictionary containing:
                - success: Whether analysis completed successfully
                - feature_name: Name of analyzed feature
                - tickets_found: Number of tickets analyzed
                - current_analysis: LLM analysis of current approach
                - best_practice_evaluation: LLM evaluation and recommendations
                - metadata: Analysis metadata and statistics
                - error: Error message if failed
        """
        if not feature_name or not feature_name.strip():
            return {
                'success': False,
                'error': 'Feature name cannot be empty'
            }
        
        feature_name = feature_name.strip()
        
        print(f"\n{'='*70}")
        print(f"FEATURE ANALYSIS: {feature_name}")
        print(f"{'='*70}\n")
        
        print(f"[Step 1/3] Searching for tickets related to '{feature_name}'...")
        
        try:
            feature_context = self.filter.get_feature_context(
                feature_name=feature_name,
                use_smart_filter=use_smart_filter,
                llm_client=self.llm if use_smart_filter else None,
                include_done=include_done
            )
            
            if feature_context.get('total_tickets', 0) == 0:
                return {
                    'success': False,
                    'feature_name': feature_name,
                    'error': f"No tickets found for feature '{feature_name}'. Try a different feature name or check your workspace data.",
                    'tickets_found': 0
                }
            
            tickets = feature_context['tickets']
            total_tickets = feature_context['total_tickets']
            
            print(f"  ✓ Found {total_tickets} tickets across {feature_context['projects_involved']} projects")
            print(f"  ✓ Involving {feature_context['team_members_involved']} team members")
            
            if use_smart_filter:
                print(f"  ✓ Validated {feature_context['validated_matches']} of {feature_context['keyword_matches']} keyword matches\n")
            else:
                print()
            
        except Exception as e:
            return {
                'success': False,
                'feature_name': feature_name,
                'error': f"Error finding tickets: {str(e)}",
                'tickets_found': 0
            }
        
        print(f"[Step 2/3] Analyzing current development approach for '{feature_name}'...")
        
        try:
            context_parts = [
                f"# Feature Analysis: {feature_name}",
                f"\n**Total Tickets Analyzed:** {total_tickets}",
                f"**Projects Involved:** {feature_context['projects_involved']}",
                f"**Team Members Involved:** {feature_context['team_members_involved']}",
                f"\n**Status Breakdown:**"
            ]
            
            for status, count in feature_context['status_breakdown'].items():
                context_parts.append(f"- {status}: {count}")
            
            context_parts.append(f"\n**Type Breakdown:**")
            for ticket_type, count in feature_context['type_breakdown'].items():
                context_parts.append(f"- {ticket_type}: {count}")
            
            context_parts.append(f"\n**Project Distribution:**")
            for project, count in sorted(feature_context['project_breakdown'].items(), key=lambda x: x[1], reverse=True):
                context_parts.append(f"- {project}: {count} tickets")
            
            if feature_context['overdue_count'] > 0:
                context_parts.append(f"\n**⚠️ Overdue Tickets:** {feature_context['overdue_count']}")
            
            if feature_context['blocked_count'] > 0:
                context_parts.append(f"**🚫 Blocked Tickets:** {feature_context['blocked_count']}")
            
            context_parts.append("\n---\n")
            
            fitted_tickets, _ = self.structurer.fit_to_token_limit(
                tickets,
                format_type='markdown',
                include_descriptions=True,
                reserve_tokens=2000
            )
            
            context_parts.append(f"# Detailed Ticket Analysis ({len(fitted_tickets)} tickets)\n")
            context_parts.append(
                self.structurer.format_tickets_markdown(
                    fitted_tickets,
                    include_descriptions=True,
                    add_summary=False
                )
            )
            
            current_analysis_prompt = "\n".join(context_parts)
            
            system_prompt_current = get_prompt(
                'feature_current_analysis',
                feature_name=feature_name
            )
            
            current_response = self._call_llm(
                prompt=current_analysis_prompt,
                system_prompt=system_prompt_current,
                temperature=0.7
            )
            
            if not current_response['success']:
                return {
                    'success': False,
                    'feature_name': feature_name,
                    'tickets_found': total_tickets,
                    'error': f"Failed to analyze current approach: {current_response.get('error', 'Unknown error')}"
                }
            
            current_analysis = current_response['insights']
            print(f"  ✓ Current approach analysis complete ({len(current_analysis)} characters)\n")
            
        except Exception as e:
            return {
                'success': False,
                'feature_name': feature_name,
                'tickets_found': total_tickets,
                'error': f"Error analyzing current approach: {str(e)}"
            }
        
        print(f"[Step 3/3] Evaluating against industry best practices...")
        
        try:
            best_practice_prompt_parts = []
            
            best_practice_prompt_parts.append(f"# Current Development Approach for {feature_name}\n")
            best_practice_prompt_parts.append(current_analysis)
            best_practice_prompt_parts.append("\n---\n")
            
            if self.best_practices_content:
                best_practice_prompt_parts.append("# Company Best Practices Reference\n")
                best_practice_prompt_parts.append(self.best_practices_content)
                best_practice_prompt_parts.append("\n---\n")
            
            best_practice_prompt_parts.append("# Evaluation Request\n")
            
            if self.best_practices_content:
                best_practice_prompt_parts.append(
                    f"Using the Company Best Practices Reference document provided above, "
                    f"please evaluate the current development approach for the '{feature_name}' feature.\n\n"
                    f"Your evaluation should:\n"
                    f"1. Identify which specific best practices from the reference document apply to this feature\n"
                    f"2. Assess how well the current approach aligns with those practices\n"
                    f"3. Highlight gaps or deviations from recommended practices\n"
                    f"4. Provide specific, actionable recommendations with reasoning\n"
                    f"5. Explain which tools, processes, or methodologies from the best practices should be adopted\n"
                    f"6. Prioritize recommendations by impact and feasibility\n\n"
                    f"Focus on practices most relevant to the '{feature_name}' feature type and current development stage."
                )
            else:
                best_practice_prompt_parts.append(
                    f"Please evaluate the current development approach for the '{feature_name}' feature against:\n"
                    f"1. General software engineering best practices\n"
                    f"2. Domain-specific industry standards for {feature_name} features\n"
                    f"3. Scalability, security, and maintainability considerations\n\n"
                    f"Provide specific, actionable recommendations for improvement."
                )
            
            best_practice_prompt = "\n".join(best_practice_prompt_parts)
            
            system_prompt_best_practice = get_prompt(
                'feature_best_practice',
                feature_name=feature_name
            )
            
            best_practice_response = self._call_llm(
                prompt=best_practice_prompt,
                system_prompt=system_prompt_best_practice,
                temperature=0.7
            )
            
            if not best_practice_response['success']:
                return {
                    'success': False,
                    'feature_name': feature_name,
                    'tickets_found': total_tickets,
                    'current_analysis': current_analysis,
                    'error': f"Failed to evaluate best practices: {best_practice_response.get('error', 'Unknown error')}"
                }
            
            best_practice_evaluation = best_practice_response['insights']
            print(f"  ✓ Best practice evaluation complete ({len(best_practice_evaluation)} characters)\n")
            
        except Exception as e:
            return {
                'success': False,
                'feature_name': feature_name,
                'tickets_found': total_tickets,
                'current_analysis': current_analysis,
                'error': f"Error evaluating best practices: {str(e)}"
            }
        
        if save_outputs:
            try:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                current_filename = f"feature_{feature_name.replace(' ', '_')}_current_{timestamp}.md"
                current_filepath = self.output_dir / current_filename
                with open(current_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Current Development Approach: {feature_name}\n\n")
                    f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"**Tickets Analyzed:** {total_tickets}\n")
                    f.write(f"**Projects Involved:** {feature_context['projects_involved']}\n\n")
                    f.write("---\n\n")
                    f.write(current_analysis)
                
                best_practice_filename = f"feature_{feature_name.replace(' ', '_')}_best_practice_{timestamp}.md"
                best_practice_filepath = self.output_dir / best_practice_filename
                with open(best_practice_filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# Best Practice Evaluation: {feature_name}\n\n")
                    f.write(f"**Analysis Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"**Tickets Analyzed:** {total_tickets}\n\n")
                    f.write("---\n\n")
                    f.write(best_practice_evaluation)
                
                print(f"✓ Saved current analysis to: {current_filepath}")
                print(f"✓ Saved best practice evaluation to: {best_practice_filepath}\n")
                
            except Exception as e:
                print(f"⚠ Warning: Failed to save outputs to files: {e}\n")
        
        return {
            'success': True,
            'feature_name': feature_name,
            'tickets_found': total_tickets,
            'current_analysis': current_analysis,
            'best_practice_evaluation': best_practice_evaluation,
            'metadata': {
                'total_tickets': total_tickets,
                'projects_involved': feature_context['projects_involved'],
                'team_members_involved': feature_context['team_members_involved'],
                'status_breakdown': feature_context['status_breakdown'],
                'type_breakdown': feature_context['type_breakdown'],
                'project_breakdown': feature_context['project_breakdown'],
                'overdue_count': feature_context['overdue_count'],
                'blocked_count': feature_context['blocked_count'],
                'high_priority_count': feature_context['high_priority_count'],
                'keyword_matches': feature_context.get('keyword_matches', total_tickets),
                'validated_matches': feature_context.get('validated_matches', total_tickets),
                'used_smart_filter': use_smart_filter,
                'included_done_tickets': include_done,
                'used_best_practices_document': self.best_practices_content is not None,
                'generated_at': datetime.now().isoformat(),
                'llm_provider': self.llm.provider,
                'llm_model': self.llm.model
            }
        }
