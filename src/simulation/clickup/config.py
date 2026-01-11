"""
Configuration for ClickUp Ticket Insights Simulation
Settings for AI-powered ticket analysis
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# PROJECT PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
SIMULATION_ROOT = SRC_ROOT / "simulation" / "clickup"
DATASETS_DIR = SIMULATION_ROOT / "datasets"
INSIGHTS_OUTPUT_DIR = DATASETS_DIR / "insights"
BEST_PRACTICES_PATH = 'src/simulation/clickup/md/best_practices.md'

DATASETS_DIR.mkdir(parents=True, exist_ok=True)
INSIGHTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATA GENERATION SETTINGS
# ============================================================================

NUM_PROJECTS = 20
NUM_USERS = 60
NUM_TICKETS = 2000

TICKET_STATUS_DISTRIBUTION = {
    'to do': 0.30,
    'in progress': 0.45,
    'blocked': 0.10,
    'done': 0.15
}

TICKET_PRIORITY_DISTRIBUTION = {
    'low': 0.20,
    'medium': 0.50,
    'high': 0.25,
    'urgent': 0.05
}

TICKET_AGE_RANGE = (1, 90)
DUE_DATE_RANGE = (-30, 60)

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')
LLM_API_KEY = os.getenv('LLM_API_KEY', '')

LLM_MODELS = {
    'openai': 'gpt-4o',
    'anthropic': 'claude-3-5-sonnet-20241022',
    'google': 'gemini-1.5-pro'
}

MAX_TOKENS_INPUT = 32000
MAX_TOKENS_OUTPUT = 8000

# ============================================================================
# DATASET FILE PATHS
# ============================================================================

FAKE_PROJECTS_FILE = DATASETS_DIR / "fake_projects.json"
FAKE_USERS_FILE = DATASETS_DIR / "fake_users.json"
FAKE_TICKETS_FILE = DATASETS_DIR / "fake_tickets.json"

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate critical configuration settings"""
    errors = []
    
    if LLM_PROVIDER and not LLM_API_KEY:
        errors.append(f"LLM_API_KEY not configured for provider: {LLM_PROVIDER}")
    
    if not DATASETS_DIR.exists():
        errors.append("DATASETS_DIR does not exist")
    
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")
    
    return True

# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    'PROJECT_ROOT',
    'SIMULATION_ROOT',
    'DATASETS_DIR',
    'INSIGHTS_OUTPUT_DIR',
    'BEST_PRACTICES_PATH',
    'NUM_PROJECTS',
    'NUM_USERS',
    'NUM_TICKETS',
    'TICKET_STATUS_DISTRIBUTION',
    'TICKET_PRIORITY_DISTRIBUTION',
    'TICKET_AGE_RANGE',
    'DUE_DATE_RANGE',
    'LLM_PROVIDER',
    'LLM_API_KEY',
    'LLM_MODELS',
    'MAX_TOKENS_INPUT',
    'MAX_TOKENS_OUTPUT',
    'FAKE_PROJECTS_FILE',
    'FAKE_USERS_FILE',
    'FAKE_TICKETS_FILE',
    'LOG_LEVEL',
    'LOG_FORMAT',
    'validate_config'
]
