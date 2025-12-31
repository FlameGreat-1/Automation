"""
Ticket Data Structurer
Formats ticket data optimally for LLM analysis and insights generation
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

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
            else:
                formatted = self.format_ticket_markdown(ticket, include_description=include_descriptions)
            
            ticket_tokens = self.estimate_tokens(formatted)
            
            if current_tokens + ticket_tokens > available_tokens:
                break
            
            fitted_tickets.append(ticket)
            current_tokens += ticket_tokens
        
        return fitted_tickets, current_tokens
    
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
