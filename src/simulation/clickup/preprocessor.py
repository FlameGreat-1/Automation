"""
Ticket Data Preprocessor
Analyzes ticket data to extract topics, patterns, and insights for LLM
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Set
from collections import Counter, defaultdict
from pathlib import Path
import re

from config import (
    FAKE_PROJECTS_FILE, FAKE_USERS_FILE, FAKE_TICKETS_FILE, DATASETS_DIR
)


class TicketPreprocessor:
    """Analyzes ticket data for patterns and insights"""
    
    def __init__(self):
        self.projects = []
        self.users = []
        self.tickets = []
        self.now = datetime.now()
        
    def load_data(self) -> tuple:
        """Load generated data from JSON files"""
        try:
            with open(FAKE_PROJECTS_FILE, 'r', encoding='utf-8') as f:
                self.projects = json.load(f)
            
            with open(FAKE_USERS_FILE, 'r', encoding='utf-8') as f:
                self.users = json.load(f)
            
            with open(FAKE_TICKETS_FILE, 'r', encoding='utf-8') as f:
                self.tickets = json.load(f)
            
            return True, f"Loaded {len(self.projects)} projects, {len(self.users)} users, {len(self.tickets)} tickets"
        except Exception as e:
            return False, f"Error loading data: {e}"
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        if not text:
            return []
        
        text = text.lower()
        
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'must', 'can', 'this',
            'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'what', 'which', 'who', 'when', 'where', 'why', 'how', 'all', 'each',
            'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
            'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very'
        }
        
        words = re.findall(r'\b[a-z]{3,}\b', text)
        keywords = [w for w in words if w not in stop_words]
        
        return keywords
    
    def extract_topics(self) -> Dict[str, Any]:
        """Extract topics and themes from tickets"""
        all_keywords = []
        ticket_keywords = {}
        
        for ticket in self.tickets:
            title = ticket.get('name', '')
            description = ticket.get('description', '')
            
            title_keywords = self.extract_keywords(title)
            desc_keywords = self.extract_keywords(description)
            
            keywords = title_keywords + desc_keywords
            all_keywords.extend(keywords)
            ticket_keywords[ticket['id']] = keywords
        
        keyword_freq = Counter(all_keywords)
        top_keywords = keyword_freq.most_common(30)
        
        technical_terms = {
            'api', 'database', 'authentication', 'login', 'payment', 'dashboard',
            'performance', 'security', 'integration', 'mobile', 'web', 'backend',
            'frontend', 'bug', 'error', 'crash', 'feature', 'optimization',
            'deployment', 'production', 'staging', 'testing', 'data', 'user',
            'admin', 'notification', 'report', 'export', 'import', 'search'
        }
        
        topics = defaultdict(list)
        for keyword, count in top_keywords:
            if keyword in technical_terms:
                for ticket in self.tickets:
                    if keyword in ticket_keywords.get(ticket['id'], []):
                        topics[keyword].append(ticket['id'])
        
        topic_clusters = {}
        for topic, ticket_ids in topics.items():
            if len(ticket_ids) >= 3:
                topic_clusters[topic] = {
                    'count': len(ticket_ids),
                    'ticket_ids': ticket_ids[:10],
                    'percentage': (len(ticket_ids) / len(self.tickets)) * 100
                }
        
        type_topics = defaultdict(lambda: defaultdict(int))
        for ticket in self.tickets:
            ticket_type = ticket.get('ticket_type', 'unknown')
            for keyword in ticket_keywords.get(ticket['id'], []):
                if keyword in technical_terms:
                    type_topics[ticket_type][keyword] += 1
        
        return {
            'top_keywords': top_keywords[:20],
            'topic_clusters': topic_clusters,
            'type_topics': dict(type_topics),
            'total_unique_keywords': len(keyword_freq)
        }
    
    def categorize_tickets(self) -> Dict[str, List[str]]:
        """Categorize tickets by functional area"""
        categories = {
            'Authentication & Security': ['login', 'authentication', 'password', 'security', 'auth', 'sso', '2fa', 'token'],
            'Payment & Billing': ['payment', 'billing', 'invoice', 'subscription', 'checkout', 'transaction'],
            'User Interface': ['ui', 'ux', 'design', 'layout', 'responsive', 'mobile', 'dashboard', 'interface'],
            'API & Integration': ['api', 'integration', 'webhook', 'endpoint', 'rest', 'graphql', 'sync'],
            'Data & Analytics': ['data', 'analytics', 'report', 'export', 'import', 'database', 'query'],
            'Performance': ['performance', 'optimization', 'speed', 'latency', 'cache', 'slow', 'timeout'],
            'Infrastructure': ['deployment', 'infrastructure', 'server', 'scaling', 'monitoring', 'logging'],
            'Notifications': ['notification', 'email', 'alert', 'reminder', 'message'],
            'Search & Filtering': ['search', 'filter', 'sort', 'query', 'find'],
            'Admin & Settings': ['admin', 'settings', 'configuration', 'permission', 'role', 'access']
        }
        
        categorized = defaultdict(list)
        uncategorized = []
        
        for ticket in self.tickets:
            title = ticket.get('name', '').lower()
            description = ticket.get('description', '').lower()
            text = f"{title} {description}"
            
            matched = False
            for category, keywords in categories.items():
                if any(keyword in text for keyword in keywords):
                    categorized[category].append(ticket['id'])
                    matched = True
                    break
            
            if not matched:
                uncategorized.append(ticket['id'])
        
        return {
            'categories': dict(categorized),
            'uncategorized': uncategorized,
            'category_distribution': {cat: len(tickets) for cat, tickets in categorized.items()}
        }

    def analyze_patterns(self) -> Dict[str, Any]:
        """Identify critical patterns in ticket data"""
        now_ms = int(self.now.timestamp() * 1000)
        
        overdue_tickets = []
        blocked_tickets = []
        stale_tickets = []
        high_priority_open = []
        
        for ticket in self.tickets:
            status = ticket['status']['status']
            due_date = ticket.get('due_date')
            created_date = ticket.get('date_created')
            updated_date = ticket.get('date_updated')
            priority = ticket.get('priority', {}).get('priority', 'none')
            
            if status != 'done' and due_date and due_date < now_ms:
                days_overdue = (now_ms - due_date) / (1000 * 60 * 60 * 24)
                overdue_tickets.append({
                    'id': ticket['id'],
                    'name': ticket['name'],
                    'days_overdue': int(days_overdue),
                    'priority': priority,
                    'assignee': ticket['assignees'][0]['username'] if ticket['assignees'] else 'Unassigned'
                })
            
            if status == 'blocked':
                blocked_tickets.append({
                    'id': ticket['id'],
                    'name': ticket['name'],
                    'project': ticket['_list_name'],
                    'assignee': ticket['assignees'][0]['username'] if ticket['assignees'] else 'Unassigned'
                })
            
            if status == 'in progress' and updated_date:
                days_since_update = (now_ms - updated_date) / (1000 * 60 * 60 * 24)
                if days_since_update > 14:
                    stale_tickets.append({
                        'id': ticket['id'],
                        'name': ticket['name'],
                        'days_stale': int(days_since_update),
                        'assignee': ticket['assignees'][0]['username'] if ticket['assignees'] else 'Unassigned'
                    })
            
            if status != 'done' and priority in ['high', 'urgent']:
                high_priority_open.append({
                    'id': ticket['id'],
                    'name': ticket['name'],
                    'priority': priority,
                    'status': status,
                    'assignee': ticket['assignees'][0]['username'] if ticket['assignees'] else 'Unassigned'
                })
        
        overdue_tickets.sort(key=lambda x: x['days_overdue'], reverse=True)
        stale_tickets.sort(key=lambda x: x['days_stale'], reverse=True)
        
        return {
            'overdue_tickets': overdue_tickets,
            'blocked_tickets': blocked_tickets,
            'stale_tickets': stale_tickets,
            'high_priority_open': high_priority_open,
            'critical_count': len([t for t in overdue_tickets if t['priority'] == 'urgent']),
            'blocked_count': len(blocked_tickets),
            'stale_count': len(stale_tickets)
        }
    
    def analyze_team_workload(self) -> Dict[str, Any]:
        """Analyze workload distribution across team members"""
        user_workload = defaultdict(lambda: {
            'total': 0,
            'by_status': defaultdict(int),
            'by_priority': defaultdict(int),
            'overdue': 0,
            'blocked': 0,
            'tickets': []
        })
        
        now_ms = int(self.now.timestamp() * 1000)
        
        for ticket in self.tickets:
            if not ticket['assignees']:
                continue
            
            assignee_id = ticket['assignees'][0]['id']
            assignee_username = ticket['assignees'][0]['username']
            status = ticket['status']['status']
            priority = ticket.get('priority', {}).get('priority', 'none')
            due_date = ticket.get('due_date')
            
            user_workload[assignee_username]['total'] += 1
            user_workload[assignee_username]['by_status'][status] += 1
            user_workload[assignee_username]['by_priority'][priority] += 1
            
            if status != 'done' and due_date and due_date < now_ms:
                user_workload[assignee_username]['overdue'] += 1
            
            if status == 'blocked':
                user_workload[assignee_username]['blocked'] += 1
            
            user_workload[assignee_username]['tickets'].append(ticket['id'])
        
        workload_list = []
        for username, data in user_workload.items():
            user = next((u for u in self.users if u['username'] == username), None)
            
            workload_list.append({
                'username': username,
                'role': user['role'] if user else 'Unknown',
                'department': user['department'] if user else 'Unknown',
                'total_tickets': data['total'],
                'in_progress': data['by_status'].get('in progress', 0),
                'to_do': data['by_status'].get('to do', 0),
                'blocked': data['blocked'],
                'overdue': data['overdue'],
                'high_priority': data['by_priority'].get('high', 0) + data['by_priority'].get('urgent', 0)
            })
        
        workload_list.sort(key=lambda x: x['total_tickets'], reverse=True)
        
        avg_workload = sum(w['total_tickets'] for w in workload_list) / len(workload_list) if workload_list else 0
        overloaded = [w for w in workload_list if w['total_tickets'] > avg_workload * 1.5]
        underutilized = [w for w in workload_list if w['total_tickets'] < avg_workload * 0.5]
        
        return {
            'workload_by_user': workload_list,
            'average_workload': round(avg_workload, 1),
            'max_workload': max(w['total_tickets'] for w in workload_list) if workload_list else 0,
            'min_workload': min(w['total_tickets'] for w in workload_list) if workload_list else 0,
            'overloaded_users': overloaded,
            'underutilized_users': underutilized,
            'total_active_users': len(workload_list)
        }
    
    def detect_anomalies(self) -> Dict[str, Any]:
        """Detect unusual patterns and anomalies"""
        anomalies = []
        
        project_ticket_count = defaultdict(int)
        for ticket in self.tickets:
            project_ticket_count[ticket['_list_name']] += 1
        
        avg_tickets_per_project = sum(project_ticket_count.values()) / len(project_ticket_count)
        
        for project, count in project_ticket_count.items():
            if count > avg_tickets_per_project * 2:
                anomalies.append({
                    'type': 'high_ticket_volume',
                    'severity': 'medium',
                    'description': f"Project '{project}' has {count} tickets (2x average)",
                    'project': project,
                    'count': count
                })
        
        user_blocked_count = defaultdict(int)
        for ticket in self.tickets:
            if ticket['status']['status'] == 'blocked' and ticket['assignees']:
                user_blocked_count[ticket['assignees'][0]['username']] += 1
        
        for username, count in user_blocked_count.items():
            if count >= 3:
                anomalies.append({
                    'type': 'multiple_blocked_tickets',
                    'severity': 'high',
                    'description': f"User '{username}' has {count} blocked tickets",
                    'username': username,
                    'count': count
                })
        
        now_ms = int(self.now.timestamp() * 1000)
        urgent_overdue = [
            t for t in self.tickets 
            if t.get('priority', {}).get('priority') == 'urgent' 
            and t['status']['status'] != 'done'
            and t.get('due_date') and t['due_date'] < now_ms
        ]
        
        if urgent_overdue:
            anomalies.append({
                'type': 'urgent_tickets_overdue',
                'severity': 'critical',
                'description': f"{len(urgent_overdue)} urgent tickets are overdue",
                'count': len(urgent_overdue),
                'ticket_ids': [t['id'] for t in urgent_overdue]
            })
        
        bug_ratio_by_project = {}
        for project in set(t['_list_name'] for t in self.tickets):
            project_tickets = [t for t in self.tickets if t['_list_name'] == project]
            bugs = [t for t in project_tickets if t.get('ticket_type') == 'Bug']
            
            if len(project_tickets) > 0:
                bug_ratio = len(bugs) / len(project_tickets)
                bug_ratio_by_project[project] = bug_ratio
                
                if bug_ratio > 0.6:
                    anomalies.append({
                        'type': 'high_bug_ratio',
                        'severity': 'medium',
                        'description': f"Project '{project}' has {bug_ratio:.0%} bugs (quality concern)",
                        'project': project,
                        'bug_ratio': bug_ratio
                    })
        
        return {
            'anomalies': anomalies,
            'total_anomalies': len(anomalies),
            'critical_anomalies': len([a for a in anomalies if a['severity'] == 'critical']),
            'high_anomalies': len([a for a in anomalies if a['severity'] == 'high'])
        }
    
    def generate_statistics(self) -> Dict[str, Any]:
        """Generate comprehensive statistics"""
        total_tickets = len(self.tickets)
        
        status_dist = Counter(t['status']['status'] for t in self.tickets)
        priority_dist = Counter(t.get('priority', {}).get('priority', 'none') for t in self.tickets)
        type_dist = Counter(t.get('ticket_type', 'unknown') for t in self.tickets)
        project_dist = Counter(t['_list_name'] for t in self.tickets)
        
        now_ms = int(self.now.timestamp() * 1000)
        
        completion_times = []
        for ticket in self.tickets:
            if ticket['status']['status'] == 'done' and ticket.get('date_closed') and ticket.get('date_created'):
                time_to_close = (ticket['date_closed'] - ticket['date_created']) / (1000 * 60 * 60 * 24)
                completion_times.append(time_to_close)
        
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        ticket_ages = []
        for ticket in self.tickets:
            if ticket.get('date_created'):
                age = (now_ms - ticket['date_created']) / (1000 * 60 * 60 * 24)
                ticket_ages.append(age)
        
        avg_ticket_age = sum(ticket_ages) / len(ticket_ages) if ticket_ages else 0
        
        assignee_dist = Counter()
        for ticket in self.tickets:
            if ticket['assignees']:
                assignee_dist[ticket['assignees'][0]['username']] += 1
        
        return {
            'total_tickets': total_tickets,
            'status_distribution': dict(status_dist),
            'priority_distribution': dict(priority_dist),
            'type_distribution': dict(type_dist),
            'project_distribution': dict(project_dist),
            'assignee_distribution': dict(assignee_dist.most_common(10)),
            'avg_completion_time_days': round(avg_completion_time, 1),
            'avg_ticket_age_days': round(avg_ticket_age, 1),
            'completion_rate': round((status_dist['done'] / total_tickets) * 100, 1) if total_tickets > 0 else 0,
            'blocked_rate': round((status_dist.get('blocked', 0) / total_tickets) * 100, 1) if total_tickets > 0 else 0
        }

    
    def generate_insights_summary(self, analysis_results: Dict[str, Any]) -> str:
        """Generate human-readable insights summary"""
        topics = analysis_results['topics']
        categories = analysis_results['categories']
        patterns = analysis_results['patterns']
        workload = analysis_results['workload']
        anomalies = analysis_results['anomalies']
        stats = analysis_results['statistics']
        
        summary = []
        summary.append("="*70)
        summary.append("TICKET ANALYSIS INSIGHTS SUMMARY")
        summary.append("="*70)
        
        summary.append(f"\n📊 OVERALL STATISTICS")
        summary.append(f"  Total Tickets: {stats['total_tickets']}")
        summary.append(f"  Completion Rate: {stats['completion_rate']}%")
        summary.append(f"  Avg Completion Time: {stats['avg_completion_time_days']} days")
        summary.append(f"  Avg Ticket Age: {stats['avg_ticket_age_days']} days")
        
        summary.append(f"\n🏷️  TOP TOPICS")
        for topic, data in list(topics['topic_clusters'].items())[:5]:
            summary.append(f"  {topic.upper()}: {data['count']} tickets ({data['percentage']:.1f}%)")
        
        summary.append(f"\n📂 CATEGORY DISTRIBUTION")
        for category, count in sorted(categories['category_distribution'].items(), key=lambda x: x[1], reverse=True)[:5]:
            summary.append(f"  {category}: {count} tickets")
        
        summary.append(f"\n⚠️  CRITICAL PATTERNS")
        summary.append(f"  Overdue Tickets: {len(patterns['overdue_tickets'])}")
        summary.append(f"  Blocked Tickets: {len(patterns['blocked_tickets'])}")
        summary.append(f"  Stale Tickets (>14 days): {len(patterns['stale_tickets'])}")
        summary.append(f"  High Priority Open: {len(patterns['high_priority_open'])}")
        
        if patterns['overdue_tickets']:
            summary.append(f"\n  Top 3 Most Overdue:")
            for ticket in patterns['overdue_tickets'][:3]:
                summary.append(f"    - {ticket['name'][:50]}... ({ticket['days_overdue']} days)")
        
        summary.append(f"\n👥 TEAM WORKLOAD")
        summary.append(f"  Active Team Members: {workload['total_active_users']}")
        summary.append(f"  Average Workload: {workload['average_workload']} tickets/person")
        summary.append(f"  Max Workload: {workload['max_workload']} tickets")
        summary.append(f"  Min Workload: {workload['min_workload']} tickets")
        
        if workload['overloaded_users']:
            summary.append(f"\n  Overloaded Users ({len(workload['overloaded_users'])}):")
            for user in workload['overloaded_users'][:3]:
                summary.append(f"    - {user['username']}: {user['total_tickets']} tickets ({user['blocked']} blocked, {user['overdue']} overdue)")
        
        if anomalies['anomalies']:
            summary.append(f"\n🚨 ANOMALIES DETECTED ({anomalies['total_anomalies']})")
            critical = [a for a in anomalies['anomalies'] if a['severity'] == 'critical']
            high = [a for a in anomalies['anomalies'] if a['severity'] == 'high']
            
            if critical:
                summary.append(f"  CRITICAL ({len(critical)}):")
                for anomaly in critical:
                    summary.append(f"    - {anomaly['description']}")
            
            if high:
                summary.append(f"  HIGH ({len(high)}):")
                for anomaly in high[:3]:
                    summary.append(f"    - {anomaly['description']}")
        
        summary.append("\n" + "="*70)
        
        return "\n".join(summary)
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Run complete preprocessing analysis"""
        print("\n" + "="*70)
        print("TICKET DATA PREPROCESSING & ANALYSIS")
        print("="*70)
        
        success, message = self.load_data()
        if not success:
            print(f"\n✗ {message}")
            return {}
        print(f"\n✓ {message}")
        
        print("\n[1/5] Extracting topics from tickets...")
        topics = self.extract_topics()
        print(f"✓ Identified {len(topics['topic_clusters'])} major topics")
        
        print("\n[2/5] Categorizing tickets by functional area...")
        categories = self.categorize_tickets()
        print(f"✓ Categorized {len(self.tickets) - len(categories['uncategorized'])} tickets into {len(categories['categories'])} categories")
        
        print("\n[3/5] Analyzing ticket patterns...")
        patterns = self.analyze_patterns()
        print(f"✓ Found {len(patterns['overdue_tickets'])} overdue, {len(patterns['blocked_tickets'])} blocked, {len(patterns['stale_tickets'])} stale tickets")
        
        print("\n[4/5] Analyzing team workload...")
        workload = self.analyze_team_workload()
        print(f"✓ Analyzed workload for {workload['total_active_users']} team members")
        
        print("\n[5/5] Generating statistics...")
        statistics = self.generate_statistics()
        print(f"✓ Generated comprehensive statistics")
        
        anomalies = self.detect_anomalies()
        
        analysis_results = {
            'topics': topics,
            'categories': categories,
            'patterns': patterns,
            'workload': workload,
            'anomalies': anomalies,
            'statistics': statistics,
            'metadata': {
                'analysis_date': self.now.isoformat(),
                'total_projects': len(self.projects),
                'total_users': len(self.users),
                'total_tickets': len(self.tickets)
            }
        }
        
        summary = self.generate_insights_summary(analysis_results)
        print(f"\n{summary}")
        
        output_file = DATASETS_DIR / "analysis_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(analysis_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Analysis complete! Results saved to: {output_file.name}")
        
        return analysis_results


if __name__ == "__main__":
    preprocessor = TicketPreprocessor()
    preprocessor.run_full_analysis()
