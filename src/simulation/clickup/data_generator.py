"""
Fake Ticket Data Generator
Generates realistic, connected ticket data for AI analysis
"""

import json
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path
import uuid

from config import (
    NUM_PROJECTS, NUM_USERS, NUM_TICKETS,
    TICKET_STATUS_DISTRIBUTION, TICKET_PRIORITY_DISTRIBUTION,
    TICKET_AGE_RANGE, DUE_DATE_RANGE,
    FAKE_PROJECTS_FILE, FAKE_USERS_FILE, FAKE_TICKETS_FILE
)


COMPANY_NAME = "TechCorp Solutions"
WORKSPACE_ID = "90182215816"
WORKSPACE_NAME = "TechCorp Workspace"


DEPARTMENTS = [
    "Engineering", "Product", "Design", "Marketing", 
    "Sales", "Customer Success", "Operations"
]

ENGINEERING_ROLES = [
    "Senior Backend Engineer", "Frontend Engineer", "DevOps Engineer",
    "QA Engineer", "Mobile Developer", "Data Engineer"
]

PRODUCT_ROLES = ["Product Manager", "Product Owner", "Business Analyst"]
DESIGN_ROLES = ["UI/UX Designer", "Product Designer", "Design Lead"]
OTHER_ROLES = ["Marketing Manager", "Sales Engineer", "Customer Success Manager"]


PROJECT_TYPES = {
    "Platform": {
        "description": "Core platform development and infrastructure",
        "common_tasks": ["API development", "Database optimization", "Infrastructure scaling", "Security hardening"]
    },
    "Mobile App": {
        "description": "iOS and Android mobile application",
        "common_tasks": ["Feature development", "Bug fixes", "Performance optimization", "UI improvements"]
    },
    "Web Dashboard": {
        "description": "Customer-facing web dashboard",
        "common_tasks": ["Dashboard features", "Analytics integration", "UI/UX improvements", "Responsive design"]
    },
    "Integration": {
        "description": "Third-party integrations and APIs",
        "common_tasks": ["API integration", "Webhook setup", "Data sync", "Authentication"]
    },
    "Internal Tools": {
        "description": "Internal tooling and automation",
        "common_tasks": ["Admin tools", "Automation scripts", "Reporting tools", "Developer tools"]
    }
}


TICKET_TYPES = {
    "Bug": {
        "weight": 0.35,
        "title_templates": [
            "{component} not working on {platform}",
            "{action} fails when {condition}",
            "Error in {feature} after {event}",
            "{component} crashes on {platform}",
            "Data inconsistency in {feature}"
        ],
        "components": ["Login", "Payment", "Dashboard", "API", "Search", "Notifications", "Reports"],
        "platforms": ["mobile", "web", "iOS", "Android", "production", "staging"],
        "actions": ["Submit", "Save", "Delete", "Update", "Export", "Import"],
        "conditions": ["large dataset", "slow network", "multiple users", "special characters"],
        "events": ["deployment", "update", "migration", "configuration change"]
    },
    "Feature": {
        "weight": 0.40,
        "title_templates": [
            "Add {feature} to {component}",
            "Implement {capability} for {user_type}",
            "Build {feature} integration",
            "Create {component} for {purpose}",
            "Enhance {feature} with {improvement}"
        ],
        "features": ["export functionality", "bulk actions", "advanced filters", "real-time updates", "notifications"],
        "components": ["dashboard", "settings", "profile", "admin panel", "API"],
        "capabilities": ["SSO", "2FA", "role-based access", "audit logging", "data export"],
        "user_types": ["admin users", "end users", "enterprise clients", "mobile users"],
        "improvements": ["better UX", "performance optimization", "accessibility", "mobile support"]
    },
    "Task": {
        "weight": 0.15,
        "title_templates": [
            "Update {item} for {reason}",
            "Refactor {component} code",
            "Optimize {feature} performance",
            "Document {feature} API",
            "Setup {infrastructure} for {environment}"
        ],
        "items": ["dependencies", "documentation", "configuration", "database schema"],
        "reasons": ["security", "compliance", "performance", "maintainability"],
        "infrastructure": ["CI/CD pipeline", "monitoring", "logging", "backup system"]
    },
    "Improvement": {
        "weight": 0.10,
        "title_templates": [
            "Improve {aspect} of {feature}",
            "Reduce {metric} in {component}",
            "Enhance {quality} for {feature}",
            "Optimize {resource} usage"
        ],
        "aspects": ["performance", "security", "usability", "reliability"],
        "metrics": ["load time", "memory usage", "API latency", "error rate"],
        "qualities": ["code quality", "test coverage", "documentation", "error handling"],
        "resources": ["database", "API", "cache", "storage"]
    }
}


CUSTOM_FIELD_TEMPLATES = {
    "Story Points": {"type": "number", "values": [1, 2, 3, 5, 8, 13]},
    "Sprint": {"type": "short_text", "values": ["Sprint 24", "Sprint 25", "Sprint 26"]},
    "Team": {"type": "drop_down", "values": ["Backend", "Frontend", "Mobile", "DevOps", "QA"]},
    "Severity": {"type": "drop_down", "values": ["Critical", "High", "Medium", "Low"]},
    "Environment": {"type": "drop_down", "values": ["Production", "Staging", "Development"]},
    "Approved": {"type": "checkbox", "values": [True, False]},
    "Target Release": {"type": "short_text", "values": ["v2.1", "v2.2", "v3.0"]},
    "Customer Impact": {"type": "drop_down", "values": ["High", "Medium", "Low", "None"]}
}


def generate_realistic_id(prefix: str = "") -> str:
    """Generate realistic ClickUp-style ID"""
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    return prefix + ''.join(random.choices(chars, k=9))


def weighted_random_choice(distribution: Dict[str, float]) -> str:
    """Select item based on weighted distribution"""
    items = list(distribution.keys())
    weights = list(distribution.values())
    return random.choices(items, weights=weights, k=1)[0]


def generate_realistic_date(days_ago_range: tuple) -> int:
    """Generate realistic timestamp (ClickUp uses milliseconds)"""
    days_ago = random.randint(days_ago_range[0], days_ago_range[1])
    date = datetime.now() - timedelta(days=days_ago)
    return int(date.timestamp() * 1000)


def generate_due_date(created_date: int, status: str) -> int:
    """Generate realistic due date based on creation date and status"""
    created_dt = datetime.fromtimestamp(created_date / 1000)
    
    if status == "done":
        days_ahead = random.randint(5, 20)
    elif status == "blocked":
        days_ahead = random.randint(-10, 5)
    elif status == "in progress":
        days_ahead = random.randint(0, 15)
    else:
        days_ahead = random.randint(5, 30)
    
    due_dt = created_dt + timedelta(days=days_ahead)
    return int(due_dt.timestamp() * 1000)


def generate_projects() -> List[Dict[str, Any]]:
    """Generate realistic project data"""
    projects = []
    project_types = list(PROJECT_TYPES.keys())
    
    project_counters = {ptype: 1 for ptype in project_types}
    
    for i in range(NUM_PROJECTS):
        project_type = project_types[i % len(project_types)]
        project_info = PROJECT_TYPES[project_type]
        
        space_id = generate_realistic_id()
        list_id = generate_realistic_id()
        
        project_number = project_counters[project_type]
        project_counters[project_type] += 1
        
        if project_number > 1:
            project_name = f"{project_type} v{project_number}"
        else:
            project_name = project_type
        
        project = {
            "space_id": space_id,
            "space_name": f"{project_type} Team",
            "list_id": list_id,
            "list_name": project_name,
            "description": project_info["description"],
            "common_tasks": project_info["common_tasks"],
            "created_date": generate_realistic_date((90, 180))
        }
        
        projects.append(project)
    
    return projects

def generate_users() -> List[Dict[str, Any]]:
    """Generate realistic user data with roles and departments"""
    users = []
    
    engineering_count = int(NUM_USERS * 0.50)
    product_count = int(NUM_USERS * 0.15)
    design_count = int(NUM_USERS * 0.15)
    other_count = NUM_USERS - engineering_count - product_count - design_count
    
    role_distribution = [
        (ENGINEERING_ROLES, engineering_count),
        (PRODUCT_ROLES, product_count),
        (DESIGN_ROLES, design_count),
        (OTHER_ROLES, other_count)
    ]
    
    user_id_counter = 266541300
    
    for roles, count in role_distribution:
        for i in range(count):
            role = random.choice(roles)
            
            if role in ENGINEERING_ROLES:
                department = "Engineering"
            elif role in PRODUCT_ROLES:
                department = "Product"
            elif role in DESIGN_ROLES:
                department = "Design"
            else:
                department = random.choice(["Marketing", "Sales", "Customer Success"])
            
            first_names = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn", 
                          "Skyler", "Cameron", "Drew", "Sage", "Rowan", "Finley", "Reese", "Parker",
                          "Emerson", "Dakota", "River", "Phoenix", "Blake", "Charlie", "Dylan", "Hayden",
                          "Jamie", "Jesse", "Kai", "Logan", "Max", "Noah", "Oakley", "Peyton",
                          "Remy", "Sam", "Tatum", "Val", "Winter", "Zion", "Adrian", "Bailey"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                         "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
                         "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "White", "Harris",
                         "Clark", "Lewis", "Robinson", "Walker", "Hall", "Allen", "Young", "King"]
            
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"{first_name.lower()}.{last_name.lower()}"
            
            user = {
                "id": str(user_id_counter),
                "username": username,
                "email": f"{username}@techcorp.com",
                "role": role,
                "department": department,
                "capacity": random.randint(5, 12),
                "created_date": generate_realistic_date((180, 365))
            }
            
            users.append(user)
            user_id_counter += 1
    
    return users


def generate_ticket_title(ticket_type: str, project: Dict) -> str:
    """Generate realistic ticket title based on type and project"""
    type_config = TICKET_TYPES[ticket_type]
    template = random.choice(type_config["title_templates"])
    
    replacements = {}
    
    placeholder_mapping = {
        'component': 'components',
        'platform': 'platforms',
        'action': 'actions',
        'condition': 'conditions',
        'event': 'events',
        'feature': 'features',
        'capability': 'capabilities',
        'user_type': 'user_types',
        'improvement': 'improvements',
        'item': 'items',
        'reason': 'reasons',
        'infrastructure': 'infrastructure',
        'aspect': 'aspects',
        'metric': 'metrics',
        'quality': 'qualities',
        'resource': 'resources',
        'purpose': 'common_tasks',
        'environment': 'platforms'
    }
    
    for placeholder, config_key in placeholder_mapping.items():
        if f"{{{placeholder}}}" in template:
            if config_key in type_config:
                replacements[placeholder] = random.choice(type_config[config_key])
            elif config_key == 'common_tasks':
                replacements[placeholder] = random.choice(project["common_tasks"])
            elif config_key == 'infrastructure':
                replacements[placeholder] = random.choice(["CI/CD pipeline", "monitoring", "logging", "backup system"])
            else:
                replacements[placeholder] = "system"
    
    try:
        title = template.format(**replacements)
        return title
    except KeyError as e:
        return f"{ticket_type}: {random.choice(project['common_tasks'])}"

def generate_ticket_description(ticket_type: str, title: str, project: Dict) -> str:
    """Generate realistic ticket description"""
    descriptions = {
        "Bug": [
            f"**Issue:** {title}\n\n**Steps to Reproduce:**\n1. Navigate to the affected area\n2. Perform the action\n3. Observe the error\n\n**Expected:** Should work correctly\n**Actual:** Error occurs\n\n**Impact:** Affects user workflow",
            f"**Problem:** {title}\n\n**Environment:** Production\n**Frequency:** Intermittent\n**Users Affected:** Multiple\n\n**Additional Context:** This started after the recent deployment.",
            f"**Bug Report:** {title}\n\n**Severity:** Medium\n**Browser/Device:** Multiple\n**Error Message:** See attached logs\n\n**Workaround:** None currently available"
        ],
        "Feature": [
            f"**Feature Request:** {title}\n\n**Business Value:** Improves user experience and efficiency\n**User Story:** As a user, I want to {title.lower()} so that I can work more efficiently\n\n**Acceptance Criteria:**\n- Feature works as expected\n- Proper error handling\n- Unit tests added",
            f"**New Feature:** {title}\n\n**Requirements:**\n- Must integrate with existing system\n- Should be scalable\n- Needs proper documentation\n\n**Technical Notes:** Consider performance implications",
            f"**Enhancement:** {title}\n\n**Rationale:** Customer feedback indicates this would significantly improve usability\n\n**Dependencies:** Requires API changes\n**Estimated Effort:** Medium"
        ],
        "Task": [
            f"**Task:** {title}\n\n**Objective:** Complete this task to improve system quality\n**Checklist:**\n- [ ] Review current implementation\n- [ ] Make necessary changes\n- [ ] Test thoroughly\n- [ ] Update documentation",
            f"**Action Item:** {title}\n\n**Context:** Part of ongoing maintenance and improvement efforts\n**Priority:** Should be completed this sprint",
            f"**Technical Task:** {title}\n\n**Details:** This is necessary for maintaining code quality and system health\n**Estimated Time:** 4-8 hours"
        ],
        "Improvement": [
            f"**Improvement:** {title}\n\n**Current State:** System works but could be better\n**Proposed Change:** {title}\n**Expected Outcome:** Better performance and user experience",
            f"**Optimization:** {title}\n\n**Metrics to Improve:**\n- Response time\n- Resource usage\n- User satisfaction\n\n**Approach:** Incremental improvements",
            f"**Enhancement:** {title}\n\n**Goal:** Make the system more efficient and maintainable\n**Success Criteria:** Measurable improvement in key metrics"
        ]
    }
    
    return random.choice(descriptions[ticket_type])


USER_WORKLOAD = {}

def assign_ticket_to_user(users: List[Dict], project: Dict, ticket_type: str) -> str:
    """Assign ticket to appropriate user based on role and capacity"""
    global USER_WORKLOAD
    
    if ticket_type == "Bug":
        eligible_roles = ENGINEERING_ROLES + ["QA Engineer"]
    elif ticket_type == "Feature":
        eligible_roles = ENGINEERING_ROLES + PRODUCT_ROLES
    elif ticket_type == "Task":
        eligible_roles = ENGINEERING_ROLES
    else:
        eligible_roles = ENGINEERING_ROLES + DESIGN_ROLES
    
    eligible_users = [u for u in users if u["role"] in eligible_roles]
    
    if not eligible_users:
        eligible_users = users
    
    if not USER_WORKLOAD:
        USER_WORKLOAD = {u["id"]: 0 for u in users}
    
    selected_user = min(eligible_users, key=lambda u: USER_WORKLOAD.get(u["id"], 0))
    USER_WORKLOAD[selected_user["id"]] += 1
    
    return selected_user["id"]

def generate_custom_fields(ticket_type: str, status: str, priority: str) -> List[Dict[str, Any]]:
    """Generate realistic custom fields for ticket"""
    custom_fields = []
    
    field_id_base = "cf-" + str(random.randint(100000, 999999))
    
    if ticket_type in ["Feature", "Improvement"]:
        custom_fields.append({
            "id": field_id_base + "-1",
            "name": "Story Points",
            "type": "number",
            "value": str(random.choice(CUSTOM_FIELD_TEMPLATES["Story Points"]["values"])),
            "type_config": {"number_format": "en-US"}
        })
    
    if ticket_type == "Bug":
        severity = "Critical" if priority == "urgent" else random.choice(["High", "Medium", "Low"])
        custom_fields.append({
            "id": field_id_base + "-2",
            "name": "Severity",
            "type": "drop_down",
            "value": severity,
            "type_config": {"options": [{"id": str(i), "name": s} for i, s in enumerate(["Critical", "High", "Medium", "Low"])]}
        })
        
        custom_fields.append({
            "id": field_id_base + "-3",
            "name": "Environment",
            "type": "drop_down",
            "value": random.choice(CUSTOM_FIELD_TEMPLATES["Environment"]["values"]),
            "type_config": {"options": [{"id": str(i), "name": e} for i, e in enumerate(CUSTOM_FIELD_TEMPLATES["Environment"]["values"])]}
        })
    
    custom_fields.append({
        "id": field_id_base + "-4",
        "name": "Team",
        "type": "drop_down",
        "value": random.choice(CUSTOM_FIELD_TEMPLATES["Team"]["values"]),
        "type_config": {"options": [{"id": str(i), "name": t} for i, t in enumerate(CUSTOM_FIELD_TEMPLATES["Team"]["values"])]}
    })
    
    if status == "done":
        custom_fields.append({
            "id": field_id_base + "-5",
            "name": "Approved",
            "type": "checkbox",
            "value": "true",
            "type_config": {}
        })
    
    return custom_fields


def generate_tickets(projects: List[Dict], users: List[Dict]) -> List[Dict[str, Any]]:
    """Generate realistic, connected ticket data"""
    tickets = []
    ticket_dependencies = {}
    
    tickets_per_project = NUM_TICKETS // NUM_PROJECTS
    
    for project in projects:
        project_tickets = []
        
        for i in range(tickets_per_project):
            ticket_type = weighted_random_choice({k: v["weight"] for k, v in TICKET_TYPES.items()})
            status = weighted_random_choice(TICKET_STATUS_DISTRIBUTION)
            priority = weighted_random_choice(TICKET_PRIORITY_DISTRIBUTION)
            
            ticket_id = generate_realistic_id()
            created_date = generate_realistic_date(TICKET_AGE_RANGE)
            
            title = generate_ticket_title(ticket_type, project)
            description = generate_ticket_description(ticket_type, title, project)
            assignee_id = assign_ticket_to_user(users, project, ticket_type)
            assignee = next(u for u in users if u["id"] == assignee_id)
            
            due_date = generate_due_date(created_date, status)
            updated_date = created_date + random.randint(3600000, 86400000 * 7)
            
            date_closed = None
            if status == "done":
                date_closed = updated_date + random.randint(3600000, 86400000 * 2)
            
            custom_fields = generate_custom_fields(ticket_type, status, priority)
            
            ticket = {
                "id": ticket_id,
                "name": title,
                "description": description,
                "status": {"status": status},
                "priority": {"priority": priority} if priority != "none" else None,
                "due_date": due_date,
                "start_date": None,
                "date_created": created_date,
                "date_updated": updated_date,
                "date_closed": date_closed,
                "assignees": [{"id": assignee_id, "username": assignee["username"], "email": assignee["email"]}],
                "creator": {"id": random.choice(users)["id"], "username": random.choice(users)["username"]},
                "tags": [],
                "custom_fields": custom_fields,
                "url": f"https://app.clickup.com/t/{ticket_id}",
                "archived": False,
                "time_estimate": None,
                "time_spent": None,
                "_workspace_id": WORKSPACE_ID,
                "_workspace_name": WORKSPACE_NAME,
                "_space_id": project["space_id"],
                "_space_name": project["space_name"],
                "_list_id": project["list_id"],
                "_list_name": project["list_name"],
                "ticket_type": ticket_type
            }
            
            project_tickets.append(ticket)
            tickets.append(ticket)
        
        if len(project_tickets) >= 3:
            blocker_ticket = random.choice(project_tickets[:len(project_tickets)//2])
            blocked_ticket = random.choice(project_tickets[len(project_tickets)//2:])
            
            if blocked_ticket["status"]["status"] != "done":
                blocked_ticket["status"]["status"] = "blocked"
                blocked_ticket["description"] += f"\n\n**Blocked by:** #{blocker_ticket['id']}"
    
    return tickets


def save_to_json(data: List[Dict], filepath: Path, data_type: str) -> tuple:
    """Save generated data to JSON file"""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True, f"Saved {len(data)} {data_type} to {filepath.name}"
    except Exception as e:
        return False, f"Error saving {data_type}: {e}"


def validate_generated_data(projects: List[Dict], users: List[Dict], tickets: List[Dict]) -> tuple:
    """Validate generated data quality and relationships"""
    errors = []
    
    if len(projects) != NUM_PROJECTS:
        errors.append(f"Expected {NUM_PROJECTS} projects, got {len(projects)}")
    
    if len(users) != NUM_USERS:
        errors.append(f"Expected {NUM_USERS} users, got {len(users)}")
    
    if len(tickets) < NUM_TICKETS * 0.95:
        errors.append(f"Expected ~{NUM_TICKETS} tickets, got {len(tickets)}")
    
    project_ids = {p["space_id"] for p in projects}
    user_ids = {u["id"] for u in users}
    
    for ticket in tickets:
        if ticket["_space_id"] not in project_ids:
            errors.append(f"Ticket {ticket['id']} references invalid project")
            break
        
        if ticket["assignees"]:
            assignee_id = ticket["assignees"][0]["id"]
            if assignee_id not in user_ids:
                errors.append(f"Ticket {ticket['id']} references invalid user")
                break
    
    status_counts = {}
    for ticket in tickets:
        status = ticket["status"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    
    for status, expected_pct in TICKET_STATUS_DISTRIBUTION.items():
        actual_pct = status_counts.get(status, 0) / len(tickets)
        if abs(actual_pct - expected_pct) > 0.15:
            errors.append(f"Status '{status}' distribution off: expected {expected_pct:.0%}, got {actual_pct:.0%}")
    
    return len(errors) == 0, errors


def print_generation_summary(projects: List[Dict], users: List[Dict], tickets: List[Dict]):
    """Print summary of generated data"""
    print("\n" + "="*70)
    print("DATA GENERATION SUMMARY")
    print("="*70)
    
    print(f"\n📊 Generated Data:")
    print(f"  Projects: {len(projects)}")
    print(f"  Users: {len(users)}")
    print(f"  Tickets: {len(tickets)}")
    
    print(f"\n👥 User Distribution:")
    dept_counts = {}
    for user in users:
        dept = user["department"]
        dept_counts[dept] = dept_counts.get(dept, 0) + 1
    for dept, count in sorted(dept_counts.items()):
        print(f"  {dept}: {count}")
    
    print(f"\n📋 Ticket Distribution:")
    status_counts = {}
    priority_counts = {}
    type_counts = {}
    
    for ticket in tickets:
        status = ticket["status"]["status"]
        status_counts[status] = status_counts.get(status, 0) + 1
        
        priority = ticket["priority"]["priority"] if ticket["priority"] else "none"
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        ticket_type = ticket.get("ticket_type", "unknown")
        type_counts[ticket_type] = type_counts.get(ticket_type, 0) + 1
    
    print(f"\n  By Status:")
    for status, count in sorted(status_counts.items()):
        pct = (count / len(tickets)) * 100
        print(f"    {status}: {count} ({pct:.1f}%)")
    
    print(f"\n  By Priority:")
    for priority, count in sorted(priority_counts.items()):
        pct = (count / len(tickets)) * 100
        print(f"    {priority}: {count} ({pct:.1f}%)")
    
    print(f"\n  By Type:")
    for ticket_type, count in sorted(type_counts.items()):
        pct = (count / len(tickets)) * 100
        print(f"    {ticket_type}: {count} ({pct:.1f}%)")
    
    blocked_count = sum(1 for t in tickets if t["status"]["status"] == "blocked")
    overdue_count = sum(1 for t in tickets if t["due_date"] < int(datetime.now().timestamp() * 1000) and t["status"]["status"] != "done")
    done_count = sum(1 for t in tickets if t["status"]["status"] == "done")
    
    print(f"\n🔍 Insights for LLM Analysis:")
    print(f"  Blocked tickets: {blocked_count}")
    print(f"  Overdue tickets: {overdue_count}")
    print(f"  Completed tickets: {done_count}")
    print(f"  In-progress tickets: {status_counts.get('in progress', 0)}")
    
    assignee_counts = {}
    for ticket in tickets:
        if ticket["assignees"]:
            assignee_id = ticket["assignees"][0]["id"]
            assignee_counts[assignee_id] = assignee_counts.get(assignee_id, 0) + 1
    
    max_tickets = max(assignee_counts.values()) if assignee_counts else 0
    min_tickets = min(assignee_counts.values()) if assignee_counts else 0
    avg_tickets = sum(assignee_counts.values()) / len(assignee_counts) if assignee_counts else 0
    
    print(f"\n  Workload Distribution:")
    print(f"    Max tickets per user: {max_tickets}")
    print(f"    Min tickets per user: {min_tickets}")
    print(f"    Avg tickets per user: {avg_tickets:.1f}")
    
    print("\n" + "="*70)


def generate_all_data():
    """Main function to generate all fake data"""
    print("\n" + "="*70)
    print("ENTERPRISE TICKET DATA GENERATOR")
    print("="*70)
    print(f"\nCompany: {COMPANY_NAME}")
    print(f"Workspace: {WORKSPACE_NAME}")
    print(f"\nGenerating realistic, connected data for AI analysis...")
    
    print(f"\n[1/3] Generating {NUM_PROJECTS} projects...")
    projects = generate_projects()
    print(f"✓ Generated {len(projects)} projects")
    
    print(f"\n[2/3] Generating {NUM_USERS} users...")
    users = generate_users()
    print(f"✓ Generated {len(users)} users")
    
    print(f"\n[3/3] Generating {NUM_TICKETS} tickets...")
    tickets = generate_tickets(projects, users)
    print(f"✓ Generated {len(tickets)} tickets")
    
    print(f"\n[4/4] Validating data quality...")
    is_valid, errors = validate_generated_data(projects, users, tickets)
    if not is_valid:
        print("\n✗ Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return False
    print("✓ Data validation passed")
    
    print(f"\n[5/5] Saving to JSON files...")
    all_success = True
    
    success, message = save_to_json(projects, FAKE_PROJECTS_FILE, "projects")
    print(f"{'✓' if success else '✗'} {message}")
    all_success &= success
    
    success, message = save_to_json(users, FAKE_USERS_FILE, "users")
    print(f"{'✓' if success else '✗'} {message}")
    all_success &= success
    
    success, message = save_to_json(tickets, FAKE_TICKETS_FILE, "tickets")
    print(f"{'✓' if success else '✗'} {message}")
    all_success &= success
    
    if all_success:
        print_generation_summary(projects, users, tickets)
        print(f"\n✓ Data generation complete!")
        print(f"\nFiles saved to:")
        print(f"  - {FAKE_PROJECTS_FILE}")
        print(f"  - {FAKE_USERS_FILE}")
        print(f"  - {FAKE_TICKETS_FILE}")
        return True
    else:
        print("\n✗ Error saving data files")
        return False


if __name__ == "__main__":
    generate_all_data()
