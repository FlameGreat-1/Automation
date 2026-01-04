class TicketFilter:
    """Filters ticket data for LLM context generation"""
    
"""
Ticket Filtering System
Filters tickets by various criteria for LLM context generation
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from pathlib import Path

from config import (
    FAKE_PROJECTS_FILE, FAKE_USERS_FILE, FAKE_TICKETS_FILE
)

class TicketFilter:
    """Filters ticket data for LLM context generation"""
    
    def __init__(self):
        self.projects = []
        self.users = []
        self.tickets = []
        self.now = datetime.now()
        self._load_data()
    
    def _load_data(self) -> bool:
        """Load ticket data from JSON files"""
        try:
            with open(FAKE_PROJECTS_FILE, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
            
            with open(FAKE_USERS_FILE, 'r', encoding='utf-8') as f:
                self.users = json.load(f)
            
            with open(FAKE_TICKETS_FILE, 'r', encoding='utf-8') as f:
                self.tickets = json.load(f)
            
            return True
        except Exception as e:
            print(f"✗ Error loading data: {e}")
            return False
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user details by username"""
        return next((u for u in self.users if u['username'] == username), None)
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user details by ID"""
        return next((u for u in self.users if u['id'] == user_id), None)
    
    def get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get project details by name"""
        return next((p for p in self.projects if p['list_name'] == project_name), None)
    
    def filter_by_project(self, project_name: str) -> List[Dict[str, Any]]:
        """Filter tickets by project name"""
        return [t for t in self.tickets if t['_list_name'] == project_name]
    
    def filter_by_assignee(self, username: str) -> List[Dict[str, Any]]:
        """Filter tickets by assignee username"""
        return [
            t for t in self.tickets 
            if t['assignees'] and t['assignees'][0]['username'] == username
        ]
    
    def filter_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Filter tickets by status"""
        valid_statuses = ['to do', 'in progress', 'blocked', 'done']
        if status not in valid_statuses:
            return []
        return [t for t in self.tickets if t['status']['status'] == status]
    
    def filter_by_priority(self, priority: str) -> List[Dict[str, Any]]:
        """Filter tickets by priority"""
        valid_priorities = ['low', 'medium', 'high', 'urgent', 'none']
        if priority not in valid_priorities:
            return []
        return [
            t for t in self.tickets 
            if t.get('priority', {}).get('priority', 'none') == priority
        ]
    
    def filter_by_type(self, ticket_type: str) -> List[Dict[str, Any]]:
        """Filter tickets by type"""
        valid_types = ['Bug', 'Feature', 'Task', 'Improvement']
        if ticket_type not in valid_types:
            return []
        return [t for t in self.tickets if t.get('ticket_type') == ticket_type]
    
    def filter_by_date_range(
        self, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None,
        date_field: str = 'date_created'
    ) -> List[Dict[str, Any]]:
        """Filter tickets by date range"""
        valid_fields = ['date_created', 'date_updated', 'date_closed', 'due_date']
        if date_field not in valid_fields:
            return []
        
        filtered = []
        for ticket in self.tickets:
            date_value = ticket.get(date_field)
            if not date_value:
                continue
            
            ticket_date = datetime.fromtimestamp(date_value / 1000)
            
            if start_date and ticket_date < start_date:
                continue
            if end_date and ticket_date > end_date:
                continue
            
            filtered.append(ticket)
        
        return filtered
    
    def filter_overdue(self) -> List[Dict[str, Any]]:
        """Get all overdue tickets"""
        now_ms = int(self.now.timestamp() * 1000)
        return [
            t for t in self.tickets 
            if t['status']['status'] != 'done' 
            and t.get('due_date') 
            and t['due_date'] < now_ms
        ]
    
    def filter_blocked(self) -> List[Dict[str, Any]]:
        """Get all blocked tickets"""
        return [t for t in self.tickets if t['status']['status'] == 'blocked']
    
    def filter_high_priority_open(self) -> List[Dict[str, Any]]:
        """Get all high/urgent priority tickets that are not done"""
        return [
            t for t in self.tickets 
            if t['status']['status'] != 'done'
            and t.get('priority', {}).get('priority') in ['high', 'urgent']
        ]

    
    def filter_stale(self, days_threshold: int = 14) -> List[Dict[str, Any]]:
        """Get tickets in progress without updates for specified days"""
        now_ms = int(self.now.timestamp() * 1000)
        threshold_ms = days_threshold * 24 * 60 * 60 * 1000
        
        stale = []
        for ticket in self.tickets:
            if ticket['status']['status'] != 'in progress':
                continue
            
            updated_date = ticket.get('date_updated')
            if not updated_date:
                continue
            
            if (now_ms - updated_date) > threshold_ms:
                stale.append(ticket)
        
        return stale
    
    def filter_unassigned(self) -> List[Dict[str, Any]]:
        """Get all unassigned tickets"""
        return [t for t in self.tickets if not t['assignees']]
    
    def filter_by_department(self, department: str) -> List[Dict[str, Any]]:
        """Get tickets assigned to users in specific department"""
        dept_users = [u['username'] for u in self.users if u['department'] == department]
        return [
            t for t in self.tickets 
            if t['assignees'] and t['assignees'][0]['username'] in dept_users
        ]
    
    def filter_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Get tickets assigned to users with specific role"""
        role_users = [u['username'] for u in self.users if u['role'] == role]
        return [
            t for t in self.tickets 
            if t['assignees'] and t['assignees'][0]['username'] in role_users
        ]
    
    def filter_due_soon(self, days_ahead: int = 7) -> List[Dict[str, Any]]:
        """Get tickets due within specified days"""
        now_ms = int(self.now.timestamp() * 1000)
        future_ms = now_ms + (days_ahead * 24 * 60 * 60 * 1000)
        
        return [
            t for t in self.tickets 
            if t['status']['status'] != 'done'
            and t.get('due_date')
            and now_ms <= t['due_date'] <= future_ms
        ]
    
    def filter_recently_created(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get tickets created within specified days"""
        now_ms = int(self.now.timestamp() * 1000)
        threshold_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)
        
        return [
            t for t in self.tickets 
            if t.get('date_created') and t['date_created'] >= threshold_ms
        ]
    
    def filter_recently_updated(self, days_back: int = 7) -> List[Dict[str, Any]]:
        """Get tickets updated within specified days"""
        now_ms = int(self.now.timestamp() * 1000)
        threshold_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)
        
        return [
            t for t in self.tickets 
            if t.get('date_updated') and t['date_updated'] >= threshold_ms
        ]
    
    def filter_by_custom_field(self, field_name: str, field_value: Any) -> List[Dict[str, Any]]:
        """Filter tickets by custom field value"""
        filtered = []
        for ticket in self.tickets:
            custom_fields = ticket.get('custom_fields', [])
            for field in custom_fields:
                if field.get('name') == field_name and field.get('value') == str(field_value):
                    filtered.append(ticket)
                    break
        return filtered
    
    def filter_multi_criteria(
        self,
        project: Optional[str] = None,
        assignee: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        ticket_type: Optional[str] = None,
        department: Optional[str] = None,
        role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter tickets by multiple criteria (AND logic)"""
        filtered = self.tickets.copy()
        
        if project:
            filtered = [t for t in filtered if t['_list_name'] == project]
        
        if assignee:
            filtered = [
                t for t in filtered 
                if t['assignees'] and t['assignees'][0]['username'] == assignee
            ]
        
        if status:
            filtered = [t for t in filtered if t['status']['status'] == status]
        
        if priority:
            filtered = [
                t for t in filtered 
                if t.get('priority', {}).get('priority', 'none') == priority
            ]
        
        if ticket_type:
            filtered = [t for t in filtered if t.get('ticket_type') == ticket_type]
        
        if department:
            dept_users = [u['username'] for u in self.users if u['department'] == department]
            filtered = [
                t for t in filtered 
                if t['assignees'] and t['assignees'][0]['username'] in dept_users
            ]
        
        if role:
            role_users = [u['username'] for u in self.users if u['role'] == role]
            filtered = [
                t for t in filtered 
                if t['assignees'] and t['assignees'][0]['username'] in role_users
            ]
        
        return filtered
    
    def filter_by_ids(self, ticket_ids: List[str]) -> List[Dict[str, Any]]:
        """Get tickets by list of IDs"""
        id_set = set(ticket_ids)
        return [t for t in self.tickets if t['id'] in id_set]
    
    def exclude_by_status(self, exclude_statuses: List[str]) -> List[Dict[str, Any]]:
        """Get all tickets except those with specified statuses"""
        return [t for t in self.tickets if t['status']['status'] not in exclude_statuses]
    
    def filter_active_work(self) -> List[Dict[str, Any]]:
        """Get all active work (to do, in progress, blocked)"""
        active_statuses = ['to do', 'in progress', 'blocked']
        return [t for t in self.tickets if t['status']['status'] in active_statuses]
    
    def get_user_context(
        self, 
        username: str, 
        include_done: bool = False,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get complete context for a user (for LLM)"""
        user = self.get_user_by_username(username)
        if not user:
            return {}
        
        user_tickets = self.filter_by_assignee(username)
        
        if not include_done:
            user_tickets = [t for t in user_tickets if t['status']['status'] != 'done']
        
        now_ms = int(self.now.timestamp() * 1000)
        threshold_ms = now_ms - (days_back * 24 * 60 * 60 * 1000)
        user_tickets = [t for t in user_tickets if t.get('date_created', 0) >= threshold_ms]
        
        overdue = [t for t in user_tickets if t.get('due_date') and t['due_date'] < now_ms and t['status']['status'] != 'done']
        blocked = [t for t in user_tickets if t['status']['status'] == 'blocked']
        in_progress = [t for t in user_tickets if t['status']['status'] == 'in progress']
        to_do = [t for t in user_tickets if t['status']['status'] == 'to do']
        high_priority = [t for t in user_tickets if t.get('priority', {}).get('priority') in ['high', 'urgent']]
        
        return {
            'user': user,
            'total_tickets': len(user_tickets),
            'all_tickets': user_tickets,
            'overdue': overdue,
            'blocked': blocked,
            'in_progress': in_progress,
            'to_do': to_do,
            'high_priority': high_priority,
            'overdue_count': len(overdue),
            'blocked_count': len(blocked),
            'in_progress_count': len(in_progress),
            'to_do_count': len(to_do),
            'high_priority_count': len(high_priority)
        }
    
    def get_project_context(
        self, 
        project_name: str,
        include_done: bool = False
    ) -> Dict[str, Any]:
        """Get complete context for a project (for LLM)"""
        project = self.get_project_by_name(project_name)
        if not project:
            return {}
        
        project_tickets = self.filter_by_project(project_name)
        
        if not include_done:
            project_tickets = [t for t in project_tickets if t['status']['status'] != 'done']
        
        now_ms = int(self.now.timestamp() * 1000)
        
        status_breakdown = {}
        for ticket in project_tickets:
            status = ticket['status']['status']
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        type_breakdown = {}
        for ticket in project_tickets:
            ticket_type = ticket.get('ticket_type', 'unknown')
            type_breakdown[ticket_type] = type_breakdown.get(ticket_type, 0) + 1
        
        assignee_breakdown = {}
        for ticket in project_tickets:
            if ticket['assignees']:
                assignee = ticket['assignees'][0]['username']
                assignee_breakdown[assignee] = assignee_breakdown.get(assignee, 0) + 1
        
        overdue = [t for t in project_tickets if t.get('due_date') and t['due_date'] < now_ms and t['status']['status'] != 'done']
        blocked = [t for t in project_tickets if t['status']['status'] == 'blocked']
        
        return {
            'project': project,
            'total_tickets': len(project_tickets),
            'all_tickets': project_tickets,
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
            'assignee_breakdown': assignee_breakdown,
            'overdue': overdue,
            'blocked': blocked,
            'overdue_count': len(overdue),
            'blocked_count': len(blocked)
        }
    
    def get_team_context(
        self, 
        department: str,
        include_done: bool = False
    ) -> Dict[str, Any]:
        """Get complete context for a department/team (for LLM)"""
        team_users = [u for u in self.users if u['department'] == department]
        team_tickets = self.filter_by_department(department)
        
        if not include_done:
            team_tickets = [t for t in team_tickets if t['status']['status'] != 'done']
        
        now_ms = int(self.now.timestamp() * 1000)
        
        user_workload = {}
        for user in team_users:
            user_tickets = [t for t in team_tickets if t['assignees'] and t['assignees'][0]['username'] == user['username']]
            user_workload[user['username']] = {
                'total': len(user_tickets),
                'overdue': len([t for t in user_tickets if t.get('due_date') and t['due_date'] < now_ms]),
                'blocked': len([t for t in user_tickets if t['status']['status'] == 'blocked'])
            }
        
        return {
            'department': department,
            'team_size': len(team_users),
            'team_members': team_users,
            'total_tickets': len(team_tickets),
            'all_tickets': team_tickets,
            'user_workload': user_workload
        }
    
    def sort_tickets(
        self, 
        tickets: List[Dict[str, Any]], 
        sort_by: str = 'priority',
        reverse: bool = True
    ) -> List[Dict[str, Any]]:
        """Sort tickets by various criteria"""
        priority_order = {'urgent': 4, 'high': 3, 'medium': 2, 'low': 1, 'none': 0}
        
        if sort_by == 'priority':
            return sorted(
                tickets, 
                key=lambda t: priority_order.get(t.get('priority', {}).get('priority', 'none'), 0),
                reverse=reverse
            )
        elif sort_by == 'due_date':
            return sorted(
                tickets,
                key=lambda t: t.get('due_date', float('inf')),
                reverse=reverse
            )
        elif sort_by == 'created_date':
            return sorted(
                tickets,
                key=lambda t: t.get('date_created', 0),
                reverse=reverse
            )
        elif sort_by == 'updated_date':
            return sorted(
                tickets,
                key=lambda t: t.get('date_updated', 0),
                reverse=reverse
            )
        else:
            return tickets
    
    def limit_tickets(
        self, 
        tickets: List[Dict[str, Any]], 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Limit number of tickets returned"""
        return tickets[:limit]
    
    def get_critical_tickets(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all critical tickets (urgent overdue or blocked high priority)"""
        now_ms = int(self.now.timestamp() * 1000)
        
        critical = []
        
        for ticket in self.tickets:
            if ticket['status']['status'] == 'done':
                continue
            
            if username and (not ticket['assignees'] or ticket['assignees'][0]['username'] != username):
                continue
            
            priority = ticket.get('priority', {}).get('priority', 'none')
            status = ticket['status']['status']
            due_date = ticket.get('due_date')
            
            is_critical = False
            
            if priority == 'urgent' and due_date and due_date < now_ms:
                is_critical = True
            
            if status == 'blocked' and priority in ['high', 'urgent']:
                is_critical = True
            
            if is_critical:
                critical.append(ticket)
        
        return self.sort_tickets(critical, sort_by='priority', reverse=True)
    
    def filter_by_feature_keyword(self, feature_name: str) -> List[Dict[str, Any]]:
        """
        Search tickets by feature name using keyword matching
        
        Searches in ticket titles, descriptions, and custom fields for the feature name.
        Case-insensitive search with support for partial matches.
        
        Args:
            feature_name: Name of the feature to search for (e.g., "Invoice", "Authentication")
        
        Returns:
            List of tickets that match the feature keyword
        
        """
        if not feature_name or not feature_name.strip():
            return []
        
        feature_keyword = feature_name.lower().strip()
        matched_tickets = []
        
        for ticket in self.tickets:
            title = ticket.get('name', '').lower()
            if feature_keyword in title:
                matched_tickets.append(ticket)
                continue
            
            description = ticket.get('description', '').lower()
            if feature_keyword in description:
                matched_tickets.append(ticket)
                continue
            
            custom_fields = ticket.get('custom_fields', [])
            for field in custom_fields:
                field_value = str(field.get('value', '')).lower()
                if feature_keyword in field_value:
                    matched_tickets.append(ticket)
                    break
        
        return matched_tickets
    
    def filter_by_feature_smart(
        self, 
        feature_name: str, 
        initial_tickets: List[Dict[str, Any]],
        llm_client: Optional[Any] = None,
        confidence_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        LLM-based intelligent validation of feature-related tickets
        
        Uses LLM to validate which tickets from initial_tickets are truly related
        to the specified feature. This catches semantically related tickets that
        keyword search might miss (e.g., "billing" for "Invoice" feature).
        
        Args:
            feature_name: Name of the feature to analyze
            initial_tickets: Tickets from keyword search to validate
            llm_client: Optional LLM client instance. If None, returns initial_tickets
            confidence_threshold: Minimum confidence score (0.0-1.0) for inclusion
        
        Returns:
            List of validated tickets that are truly related to the feature
        
        """
        if llm_client is None:
            return initial_tickets
        
        if not initial_tickets:
            return []
        
        if not feature_name or not feature_name.strip():
            return []
        
        ticket_summaries = []
        for i, ticket in enumerate(initial_tickets[:50]):  
            summary = {
                'index': i,
                'id': ticket['id'],
                'title': ticket['name'],
                'description': ticket.get('description', '')[:200],  
                'type': ticket.get('ticket_type', 'unknown'),
                'project': ticket.get('_list_name', 'unknown')
            }
            ticket_summaries.append(summary)
        
        prompt = f"""Analyze these tickets and identify which ones are related to the "{feature_name}" feature.

A ticket is related if it:
- Directly mentions {feature_name}
- Implements functionality for {feature_name}
- Fixes bugs in {feature_name}
- Has dependencies on {feature_name}
- Is semantically related (e.g., "billing" relates to "Invoice")

Tickets:
{json.dumps(ticket_summaries, indent=2)}

Respond with ONLY a JSON array of ticket indices that are related to {feature_name}.
Format: {{"related_indices": [0, 2, 5, ...]}}
"""
        
        system_prompt = """You are a software development analyst expert at identifying feature relationships in tickets.
Analyze tickets carefully and identify only those truly related to the specified feature.
Be precise but not overly strict - include semantically related tickets.
Respond with valid JSON only."""
        
        try:
            response = llm_client.call_with_retry(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3  
            )
            
            if not response.get('success'):
                return initial_tickets
            
            content = response.get('content', '').strip()
            
            result_json = llm_client.extract_json_from_response(content)
            
            if not result_json or 'related_indices' not in result_json:
                return initial_tickets
            
            related_indices = result_json['related_indices']
            
            validated_tickets = []
            for idx in related_indices:
                if 0 <= idx < len(initial_tickets):
                    validated_tickets.append(initial_tickets[idx])
            
            return validated_tickets
        
        except Exception as e:
            print(f"Warning: LLM validation failed ({e}), using keyword results")
            return initial_tickets
    
    def get_feature_context(
        self,
        feature_name: str,
        use_smart_filter: bool = True,
        llm_client: Optional[Any] = None,
        include_done: bool = False
    ) -> Dict[str, Any]:
        """
        Get complete context for a feature across the workspace
        
        Combines keyword search and optional LLM validation to find all tickets
        related to a specific feature, then provides comprehensive context.
        
        Args:
            feature_name: Name of the feature to analyze
            use_smart_filter: Whether to use LLM validation (requires llm_client)
            llm_client: LLM client instance for smart filtering
            include_done: Whether to include completed tickets
        
        Returns:
            Dictionary with feature context including tickets, statistics, and metadata
        
        """
        keyword_tickets = self.filter_by_feature_keyword(feature_name)
        
        if not keyword_tickets:
            return {
                'feature_name': feature_name,
                'total_tickets': 0,
                'tickets': [],
                'error': f'No tickets found for feature: {feature_name}'
            }
        
        if use_smart_filter and llm_client:
            validated_tickets = self.filter_by_feature_smart(
                feature_name, 
                keyword_tickets, 
                llm_client
            )
        else:
            validated_tickets = keyword_tickets
        
        if not include_done:
            validated_tickets = [
                t for t in validated_tickets 
                if t['status']['status'] != 'done'
            ]
        
        now_ms = int(datetime.now().timestamp() * 1000)
        
        status_breakdown = {}
        for ticket in validated_tickets:
            status = ticket['status']['status']
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
        
        type_breakdown = {}
        for ticket in validated_tickets:
            ticket_type = ticket.get('ticket_type', 'unknown')
            type_breakdown[ticket_type] = type_breakdown.get(ticket_type, 0) + 1
        
        project_breakdown = {}
        for ticket in validated_tickets:
            project = ticket.get('_list_name', 'unknown')
            project_breakdown[project] = project_breakdown.get(project, 0) + 1
        
        assignee_breakdown = {}
        for ticket in validated_tickets:
            if ticket['assignees']:
                assignee = ticket['assignees'][0]['username']
                assignee_breakdown[assignee] = assignee_breakdown.get(assignee, 0) + 1
        
        overdue = [
            t for t in validated_tickets 
            if t.get('due_date') and t['due_date'] < now_ms 
            and t['status']['status'] != 'done'
        ]
        
        blocked = [
            t for t in validated_tickets 
            if t['status']['status'] == 'blocked'
        ]
        
        high_priority = [
            t for t in validated_tickets 
            if t.get('priority', {}).get('priority') in ['high', 'urgent']
        ]
        
        return {
            'feature_name': feature_name,
            'total_tickets': len(validated_tickets),
            'keyword_matches': len(keyword_tickets),
            'validated_matches': len(validated_tickets),
            'tickets': validated_tickets,
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
            'project_breakdown': project_breakdown,
            'assignee_breakdown': assignee_breakdown,
            'overdue': overdue,
            'blocked': blocked,
            'high_priority': high_priority,
            'overdue_count': len(overdue),
            'blocked_count': len(blocked),
            'high_priority_count': len(high_priority),
            'projects_involved': len(project_breakdown),
            'team_members_involved': len(assignee_breakdown)
        }
    

    def get_summary(self, tickets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get summary statistics for filtered tickets"""
        if not tickets:
            return {'total': 0}
        
        status_counts = {}
        priority_counts = {}
        type_counts = {}
        
        for ticket in tickets:
            status = ticket['status']['status']
            status_counts[status] = status_counts.get(status, 0) + 1
            
            priority = ticket.get('priority', {}).get('priority', 'none')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            ticket_type = ticket.get('ticket_type', 'unknown')
            type_counts[ticket_type] = type_counts.get(ticket_type, 0) + 1
        
        now_ms = int(self.now.timestamp() * 1000)
        overdue_count = len([t for t in tickets if t.get('due_date') and t['due_date'] < now_ms and t['status']['status'] != 'done'])
        blocked_count = len([t for t in tickets if t['status']['status'] == 'blocked'])
        
        return {
            'total': len(tickets),
            'status_breakdown': status_counts,
            'priority_breakdown': priority_counts,
            'type_breakdown': type_counts,
            'overdue_count': overdue_count,
            'blocked_count': blocked_count
        }
