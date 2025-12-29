class TicketStructurer:
    """Structures ticket data optimally for LLM consumption"""
    
"""
Enterprise-Grade Ticket Data Structurer
Formats ticket data optimally for LLM analysis and insights generation
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import re

from config import MAX_TOKENS_INPUT


class TicketStructurer:
    """Structures ticket data optimally for LLM consumption"""
    
    def __init__(self, max_tokens: int = MAX_TOKENS_INPUT):
        self.max_tokens = max_tokens
        self.now = datetime.now()
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation: 1 token ≈ 4 characters)"""
        return len(text) // 4
    
    def truncate_text(self, text: str, max_length: int = 500) -> str:
        """Truncate text to maximum length"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def format_timestamp(self, timestamp_ms: Optional[int]) -> str:
        """Format timestamp to human-readable date"""
        if not timestamp_ms:
            return "N/A"
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.strftime("%Y-%m-%d")
    
    def calculate_days_difference(self, timestamp_ms: int) -> int:
        """Calculate days difference from now"""
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        diff = self.now - dt
        return diff.days
    
    def enrich_ticket_metadata(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """Add computed metadata to ticket for better LLM understanding"""
        enriched = ticket.copy()
        
        now_ms = int(self.now.timestamp() * 1000)
        
        created_date = ticket.get('date_created')
        if created_date:
            enriched['age_days'] = self.calculate_days_difference(created_date)
            enriched['created_date_formatted'] = self.format_timestamp(created_date)
        
        due_date = ticket.get('due_date')
        if due_date:
            enriched['due_date_formatted'] = self.format_timestamp(due_date)
            if due_date < now_ms and ticket['status']['status'] != 'done':
                days_overdue = (now_ms - due_date) // (1000 * 60 * 60 * 24)
                enriched['is_overdue'] = True
                enriched['days_overdue'] = int(days_overdue)
            else:
                enriched['is_overdue'] = False
        
        updated_date = ticket.get('date_updated')
        if updated_date:
            enriched['days_since_update'] = self.calculate_days_difference(updated_date)
            enriched['updated_date_formatted'] = self.format_timestamp(updated_date)
        
        status = ticket['status']['status']
        enriched['is_active'] = status in ['to do', 'in progress', 'blocked']
        enriched['is_blocked'] = status == 'blocked'
        enriched['is_done'] = status == 'done'
        
        priority = ticket.get('priority', {}).get('priority', 'none')
        enriched['is_high_priority'] = priority in ['high', 'urgent']
        enriched['is_urgent'] = priority == 'urgent'
        
        enriched['assignee_name'] = ticket['assignees'][0]['username'] if ticket['assignees'] else 'Unassigned'
        
        return enriched
    
    def format_ticket_json(self, ticket: Dict[str, Any], include_description: bool = True) -> Dict[str, Any]:
        """Format single ticket as clean JSON for LLM"""
        enriched = self.enrich_ticket_metadata(ticket)
        
        formatted = {
            'id': enriched['id'],
            'title': enriched['name'],
            'status': enriched['status']['status'],
            'priority': enriched.get('priority', {}).get('priority', 'none'),
            'type': enriched.get('ticket_type', 'unknown'),
            'project': enriched['_list_name'],
            'assignee': enriched['assignee_name'],
            'created': enriched.get('created_date_formatted', 'N/A'),
            'age_days': enriched.get('age_days', 0),
            'is_overdue': enriched.get('is_overdue', False),
            'is_blocked': enriched['is_blocked'],
            'is_high_priority': enriched['is_high_priority']
        }
        
        if enriched.get('is_overdue'):
            formatted['days_overdue'] = enriched.get('days_overdue', 0)
        
        if enriched.get('due_date_formatted'):
            formatted['due_date'] = enriched['due_date_formatted']
        
        if include_description:
            description = enriched.get('description', '')
            formatted['description'] = self.truncate_text(description, max_length=300)
        
        return formatted
    
    def format_ticket_markdown(self, ticket: Dict[str, Any], include_description: bool = True) -> str:
        """Format single ticket as Markdown for LLM"""
        enriched = self.enrich_ticket_metadata(ticket)
        
        lines = []
        lines.append(f"### {enriched['name']}")
        lines.append(f"**ID:** {enriched['id']}")
        lines.append(f"**Status:** {enriched['status']['status'].upper()}")
        lines.append(f"**Priority:** {enriched.get('priority', {}).get('priority', 'none').upper()}")
        lines.append(f"**Type:** {enriched.get('ticket_type', 'unknown')}")
        lines.append(f"**Project:** {enriched['_list_name']}")
        lines.append(f"**Assignee:** {enriched['assignee_name']}")
        lines.append(f"**Created:** {enriched.get('created_date_formatted', 'N/A')} ({enriched.get('age_days', 0)} days ago)")
        
        if enriched.get('due_date_formatted'):
            lines.append(f"**Due Date:** {enriched['due_date_formatted']}")
        
        if enriched.get('is_overdue'):
            lines.append(f"**⚠️ OVERDUE:** {enriched.get('days_overdue', 0)} days")
        
        if enriched['is_blocked']:
            lines.append(f"**🚫 BLOCKED**")
        
        if include_description and enriched.get('description'):
            lines.append(f"\n**Description:**")
            lines.append(self.truncate_text(enriched['description'], max_length=300))
        
        lines.append("")
        
        return "\n".join(lines)
    
    def format_ticket_plain_text(self, ticket: Dict[str, Any], include_description: bool = True) -> str:
        """Format single ticket as plain text for LLM"""
        enriched = self.enrich_ticket_metadata(ticket)
        
        parts = [
            f"Ticket: {enriched['name']}",
            f"ID: {enriched['id']}",
            f"Status: {enriched['status']['status']}",
            f"Priority: {enriched.get('priority', {}).get('priority', 'none')}",
            f"Type: {enriched.get('ticket_type', 'unknown')}",
            f"Project: {enriched['_list_name']}",
            f"Assignee: {enriched['assignee_name']}",
            f"Age: {enriched.get('age_days', 0)} days"
        ]
        
        if enriched.get('is_overdue'):
            parts.append(f"OVERDUE: {enriched.get('days_overdue', 0)} days")
        
        if enriched['is_blocked']:
            parts.append("BLOCKED")
        
        if include_description and enriched.get('description'):
            parts.append(f"Description: {self.truncate_text(enriched['description'], max_length=200)}")
        
        return " | ".join(parts)
    
    def format_tickets_json(
        self, 
        tickets: List[Dict[str, Any]], 
        include_descriptions: bool = False
    ) -> List[Dict[str, Any]]:
        """Format multiple tickets as JSON array"""
        return [self.format_ticket_json(t, include_description=include_descriptions) for t in tickets]
    
    def format_tickets_markdown(
        self, 
        tickets: List[Dict[str, Any]], 
        include_descriptions: bool = False,
        add_summary: bool = True
    ) -> str:
        """Format multiple tickets as Markdown document"""
        lines = []
        
        if add_summary:
            lines.append("# Ticket Summary")
            lines.append(f"\n**Total Tickets:** {len(tickets)}")
            
            status_counts = {}
            priority_counts = {}
            for ticket in tickets:
                status = ticket['status']['status']
                status_counts[status] = status_counts.get(status, 0) + 1
                
                priority = ticket.get('priority', {}).get('priority', 'none')
                priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            lines.append(f"\n**By Status:**")
            for status, count in sorted(status_counts.items()):
                lines.append(f"- {status}: {count}")
            
            lines.append(f"\n**By Priority:**")
            for priority, count in sorted(priority_counts.items()):
                lines.append(f"- {priority}: {count}")
            
            lines.append("\n---\n")
        
        lines.append("# Tickets\n")
        
        for ticket in tickets:
            lines.append(self.format_ticket_markdown(ticket, include_description=include_descriptions))
        
        return "\n".join(lines)
    
    def prioritize_tickets(self, tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prioritize tickets by importance for LLM context"""
        
        def calculate_priority_score(ticket: Dict[str, Any]) -> int:
            score = 0
            enriched = self.enrich_ticket_metadata(ticket)
            
            if enriched.get('is_urgent'):
                score += 100
            elif enriched.get('is_high_priority'):
                score += 50
            
            if enriched.get('is_overdue'):
                days_overdue = enriched.get('days_overdue', 0)
                score += min(days_overdue * 5, 50)
            
            if enriched.get('is_blocked'):
                score += 40
            
            status = enriched['status']['status']
            if status == 'in progress':
                score += 20
            elif status == 'to do':
                score += 10
            
            ticket_type = enriched.get('ticket_type', '')
            if ticket_type == 'Bug':
                score += 15
            
            return score
        
        return sorted(tickets, key=calculate_priority_score, reverse=True)
    
    def fit_to_token_limit(
        self, 
        tickets: List[Dict[str, Any]], 
        format_type: str = 'json',
        include_descriptions: bool = False,
        reserve_tokens: int = 1000
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fit tickets within token limit, prioritizing most important"""
        
        prioritized = self.prioritize_tickets(tickets)
        
        available_tokens = self.max_tokens - reserve_tokens
        
        fitted_tickets = []
        current_tokens = 0
        
        for ticket in prioritized:
            if format_type == 'json':
                formatted = json.dumps(self.format_ticket_json(ticket, include_description=include_descriptions))
            elif format_type == 'markdown':
                formatted = self.format_ticket_markdown(ticket, include_description=include_descriptions)
            else:
                formatted = self.format_ticket_plain_text(ticket, include_description=include_descriptions)
            
            ticket_tokens = self.estimate_tokens(formatted)
            
            if current_tokens + ticket_tokens > available_tokens:
                break
            
            fitted_tickets.append(ticket)
            current_tokens += ticket_tokens
        
        return fitted_tickets, current_tokens
    
    def create_llm_context(
        self,
        tickets: List[Dict[str, Any]],
        context_type: str = 'user',
        user_info: Optional[Dict[str, Any]] = None,
        project_info: Optional[Dict[str, Any]] = None,
        format_type: str = 'json',
        include_descriptions: bool = False
    ) -> Dict[str, Any]:
        """Create optimized context for LLM with metadata"""
        
        fitted_tickets, token_count = self.fit_to_token_limit(
            tickets, 
            format_type=format_type,
            include_descriptions=include_descriptions
        )
        
        context = {
            'context_type': context_type,
            'total_tickets_available': len(tickets),
            'tickets_included': len(fitted_tickets),
            'tickets_excluded': len(tickets) - len(fitted_tickets),
            'estimated_tokens': token_count,
            'format': format_type,
            'timestamp': self.now.isoformat()
        }
        
        if user_info:
            context['user'] = {
                'username': user_info.get('username'),
                'role': user_info.get('role'),
                'department': user_info.get('department')
            }
        
        if project_info:
            context['project'] = {
                'name': project_info.get('list_name'),
                'description': project_info.get('description')
            }
        
        status_breakdown = {}
        priority_breakdown = {}
        overdue_count = 0
        blocked_count = 0
        
        for ticket in fitted_tickets:
            enriched = self.enrich_ticket_metadata(ticket)
            
            status = enriched['status']['status']
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
            
            priority = enriched.get('priority', {}).get('priority', 'none')
            priority_breakdown[priority] = priority_breakdown.get(priority, 0) + 1
            
            if enriched.get('is_overdue'):
                overdue_count += 1
            if enriched.get('is_blocked'):
                blocked_count += 1
        
        context['summary'] = {
            'status_breakdown': status_breakdown,
            'priority_breakdown': priority_breakdown,
            'overdue_count': overdue_count,
            'blocked_count': blocked_count
        }
        
        if format_type == 'json':
            context['tickets'] = self.format_tickets_json(fitted_tickets, include_descriptions=include_descriptions)
        elif format_type == 'markdown':
            context['tickets'] = self.format_tickets_markdown(fitted_tickets, include_descriptions=include_descriptions)
        else:
            context['tickets'] = [self.format_ticket_plain_text(t, include_description=include_descriptions) for t in fitted_tickets]
        
        return context
    
    def create_prompt_context(
        self,
        tickets: List[Dict[str, Any]],
        question: str,
        user_info: Optional[Dict[str, Any]] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """Create complete prompt with context for LLM"""
        
        fitted_tickets, _ = self.fit_to_token_limit(tickets, format_type='markdown', include_descriptions=False)
        
        prompt_parts = []
        
        prompt_parts.append("# Context")
        
        if user_info:
            prompt_parts.append(f"\n**User:** {user_info.get('username')} ({user_info.get('role')})")
            prompt_parts.append(f"**Department:** {user_info.get('department')}")
        
        prompt_parts.append(f"\n**Date:** {self.now.strftime('%Y-%m-%d')}")
        prompt_parts.append(f"**Total Tickets:** {len(fitted_tickets)}")
        
        if additional_context:
            prompt_parts.append(f"\n**Additional Context:**\n{additional_context}")
        
        prompt_parts.append("\n---\n")
        prompt_parts.append("# Tickets\n")
        prompt_parts.append(self.format_tickets_markdown(fitted_tickets, include_descriptions=False, add_summary=False))
        
        prompt_parts.append("\n---\n")
        prompt_parts.append(f"# Question\n\n{question}")
        
        return "\n".join(prompt_parts)
    
    def create_insights_prompt(
        self,
        tickets: List[Dict[str, Any]],
        user_info: Optional[Dict[str, Any]] = None,
        focus_areas: Optional[List[str]] = None
    ) -> str:
        """Create specialized prompt for generating insights"""
        
        fitted_tickets, _ = self.fit_to_token_limit(tickets, format_type='json', include_descriptions=False)
        
        prompt_parts = []
        
        prompt_parts.append("You are an AI assistant helping a project manager analyze their team's tickets.")
        prompt_parts.append("\n# Current Situation\n")
        
        if user_info:
            prompt_parts.append(f"**Manager:** {user_info.get('username')} ({user_info.get('role')})")
        
        prompt_parts.append(f"**Date:** {self.now.strftime('%Y-%m-%d')}")
        prompt_parts.append(f"**Tickets to Analyze:** {len(fitted_tickets)}")
        
        overdue = [t for t in fitted_tickets if self.enrich_ticket_metadata(t).get('is_overdue')]
        blocked = [t for t in fitted_tickets if self.enrich_ticket_metadata(t).get('is_blocked')]
        high_priority = [t for t in fitted_tickets if self.enrich_ticket_metadata(t).get('is_high_priority')]
        
        prompt_parts.append(f"\n**Key Metrics:**")
        prompt_parts.append(f"- Overdue: {len(overdue)}")
        prompt_parts.append(f"- Blocked: {len(blocked)}")
        prompt_parts.append(f"- High Priority: {len(high_priority)}")
        
        prompt_parts.append("\n# Tickets Data\n")
        prompt_parts.append("```json")
        prompt_parts.append(json.dumps(self.format_tickets_json(fitted_tickets, include_descriptions=False), indent=2))
        prompt_parts.append("```")
        
        prompt_parts.append("\n# Task\n")
        prompt_parts.append("Analyze the tickets and provide actionable insights:")
        
        if focus_areas:
            prompt_parts.append("\nFocus on:")
            for area in focus_areas:
                prompt_parts.append(f"- {area}")
        else:
            prompt_parts.append("1. What are the most critical issues that need immediate attention?")
            prompt_parts.append("2. Are there any bottlenecks or patterns in blocked/overdue tickets?")
            prompt_parts.append("3. What should be prioritized today?")
            prompt_parts.append("4. Are there any team members who might be overloaded?")
            prompt_parts.append("5. Any recommendations for improving workflow?")
        
        return "\n".join(prompt_parts)
    
    def export_context(
        self,
        context: Dict[str, Any],
        filename: str = "llm_context.json"
    ) -> bool:
        """Export LLM context to JSON file"""
        try:
            output_path = Path(__file__).parent / "datasets" / filename
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(context, f, indent=2, ensure_ascii=False)
            print(f"✓ Exported LLM context to {filename}")
            return True
        except Exception as e:
            print(f"✗ Error exporting context: {e}")
            return False
    
    def validate_context(self, context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate LLM context structure and content"""
        errors = []
        
        if 'tickets' not in context:
            errors.append("Missing 'tickets' field")
        
        if 'context_type' not in context:
            errors.append("Missing 'context_type' field")
        
        if 'estimated_tokens' in context:
            if context['estimated_tokens'] > self.max_tokens:
                errors.append(f"Token count ({context['estimated_tokens']}) exceeds limit ({self.max_tokens})")
        
        if 'tickets' in context and isinstance(context['tickets'], list):
            if len(context['tickets']) == 0:
                errors.append("No tickets in context")
        
        return len(errors) == 0, errors


if __name__ == "__main__":
    from filter import TicketFilter
    
    print("\n" + "="*70)
    print("TICKET STRUCTURER - DEMO")
    print("="*70)
    
    filter_system = TicketFilter()
    structurer = TicketStructurer(max_tokens=8000)
    
    # Use first user from actual data
    first_user = filter_system.users[0]['username']
    user_tickets = filter_system.filter_by_assignee(first_user)
    user_info = filter_system.get_user_by_username(first_user)
    
    print(f"\n[1] Creating LLM Context (JSON format)")
    context = structurer.create_llm_context(
        tickets=user_tickets,
        context_type='user',
        user_info=user_info,
        format_type='json',
        include_descriptions=False
    )
    print(f"  Total tickets: {context['total_tickets_available']}")
    print(f"  Included: {context['tickets_included']}")
    print(f"  Estimated tokens: {context['estimated_tokens']}")
    print(f"  Summary: {context['summary']}")
    
    print(f"\n[2] Creating Insights Prompt")
    prompt = structurer.create_insights_prompt(
        tickets=user_tickets,
        user_info=user_info
    )
    print(f"  Prompt length: {len(prompt)} characters")
    print(f"  Estimated tokens: {structurer.estimate_tokens(prompt)}")
    
    print(f"\n[3] Validating Context")
    is_valid, errors = structurer.validate_context(context)
    if is_valid:
        print(f"  ✓ Context is valid")
    else:
        print(f"  ✗ Validation errors:")
        for error in errors:
            print(f"    - {error}")
    
    print("\n" + "="*70)
