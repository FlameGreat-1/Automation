"""
Configuration for ClickUp Ticket Insights Simulation
Enterprise-grade settings for AI-powered ticket analysis
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# PROJECT PATHS
# ============================================================================

# Root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
SIMULATION_ROOT = SRC_ROOT / "simulation" / "clickup"
DATASETS_DIR = SIMULATION_ROOT / "datasets"

# Ensure directories exist
DATASETS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# DATABASE CONFIGURATION (Reuse existing ClickUp database)
# ============================================================================

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'w01941c7.kasserver.com'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_NAME', 'd0458ac6'),
    'user': os.getenv('DB_USER', 'd0458ac6'),
    'password': os.getenv('DB_PASSWORD', 'LpEkJ7CEKQV3et9YeifK')
}

# Table names
TICKETS_TABLE = 'clickup_tickets'
CUSTOM_FIELDS_TABLE = 'clickup_custom_fields'
API_KEYS_TABLE = 'clickup_api_keys'

# ============================================================================
# DATA GENERATION SETTINGS
# ============================================================================

# Realistic enterprise data volumes
NUM_PROJECTS = 20
NUM_USERS = 60
NUM_TICKETS = 2000

# Ticket distribution (realistic percentages)
TICKET_STATUS_DISTRIBUTION = {
    'to do': 0.30,        # 30% not started
    'in progress': 0.45,  # 45% being worked on
    'blocked': 0.10,      # 10% blocked
    'done': 0.15          # 15% completed
}

TICKET_PRIORITY_DISTRIBUTION = {
    'low': 0.20,
    'medium': 0.50,
    'high': 0.25,
    'urgent': 0.05
}

# Date ranges (days from now)
TICKET_AGE_RANGE = (1, 90)      # Tickets created 1-90 days ago
DUE_DATE_RANGE = (-30, 60)      # Due dates from 30 days ago to 60 days ahead

# ============================================================================
# LLM CONFIGURATION
# ============================================================================

# LLM Provider (openai, anthropic, google, etc.)
LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'openai')

# API Keys (add to .env file)
LLM_API_KEY = os.getenv('LLM_API_KEY', '')

# Model settings
LLM_MODELS = {
    'openai': 'gpt-4-turbo-preview',
    'anthropic': 'claude-3-opus-20240229',
    'google': 'gemini-pro'
}

# Token limits
MAX_TOKENS_INPUT = 8000   # Max tokens to send to LLM
MAX_TOKENS_OUTPUT = 2000  # Max tokens in LLM response

# ============================================================================
# VECTOR DATABASE CONFIGURATION (For embeddings research)
# ============================================================================

# Vector DB provider (chromadb, pinecone, weaviate, faiss)
VECTOR_DB_PROVIDER = os.getenv('VECTOR_DB_PROVIDER', 'chromadb')

# ChromaDB settings (local, lightweight)
CHROMADB_PATH = SIMULATION_ROOT / "vector_db"

# Embedding model
EMBEDDING_MODEL = 'text-embedding-3-small'  # OpenAI embedding model

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
    
    # Check database config
    if not DB_CONFIG['host']:
        errors.append("DB_HOST not configured")
    if not DB_CONFIG['database']:
        errors.append("DB_NAME not configured")
    
    # Check LLM API key (only if using LLM)
    if LLM_PROVIDER and not LLM_API_KEY:
        errors.append(f"LLM_API_KEY not configured for provider: {LLM_PROVIDER}")
    
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
    'DB_CONFIG',
    'TICKETS_TABLE',
    'CUSTOM_FIELDS_TABLE',
    'NUM_PROJECTS',
    'NUM_USERS',
    'NUM_TICKETS',
    'TICKET_STATUS_DISTRIBUTION',
    'TICKET_PRIORITY_DISTRIBUTION',
    'LLM_PROVIDER',
    'LLM_API_KEY',
    'LLM_MODELS',
    'MAX_TOKENS_INPUT',
    'MAX_TOKENS_OUTPUT',
    'VECTOR_DB_PROVIDER',
    'EMBEDDING_MODEL',
    'FAKE_PROJECTS_FILE',
    'FAKE_USERS_FILE',
    'FAKE_TICKETS_FILE',
    'validate_config'
]
