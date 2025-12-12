"""
Database Connection Manager
Provides centralized, production-grade database connection handling
for all automation scripts.

Features:
- Connection pooling for performance
- Automatic reconnection on failure
- Thread-safe operations
- Environment-based configuration
- Comprehensive error handling
- Context manager support
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error, pooling

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Singleton database connection manager with connection pooling.
    
    This class manages MySQL database connections for all automation scripts,
    ensuring efficient resource usage and automatic error recovery.
    """
    
    _instance = None
    _pool = None
    _config = None
    
    def __new__(cls):
        """Singleton pattern - only one instance exists"""
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize database configuration (only once)"""
        if self._initialized:
            return
        
        # Load and validate configuration
        self._config = self._load_config()
        self._validate_config()
        
        # Create connection pool
        self._create_pool()
        
        self._initialized = True
        logger.info("✓ DatabaseConnection initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load database configuration from environment variables.
        
        Returns:
            Dict containing database configuration
            
        Raises:
            ValueError: If required environment variables are missing
        """
        config = {
            'host': os.getenv('DB_HOST'),
            'port': int(os.getenv('DB_PORT', 3306)),
            'database': os.getenv('DB_NAME'),
            'user': os.getenv('DB_USER'),
            'password': os.getenv('DB_PASSWORD'),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': False,  # Explicit transaction control
            'raise_on_warnings': True,
            'get_warnings': True,
            'connection_timeout': 30,  # 30 seconds timeout
        }
        
        return config
    
    def _validate_config(self) -> None:
        """
        Validate that all required configuration values are present.
        
        Raises:
            ValueError: If any required configuration is missing
        """
        required_keys = ['host', 'database', 'user', 'password']
        missing = [key for key in required_keys if not self._config.get(key)]
        
        if missing:
            error_msg = f"Missing required environment variables: {', '.join(f'DB_{k.upper()}' for k in missing)}"
            logger.error(f"✗ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✓ Database configuration validated for: {self._config['database']}@{self._config['host']}")
    
    def _create_pool(self) -> None:
        """
        Create connection pool for efficient connection management.
        
        Pool configuration:
        - pool_name: Unique identifier for this pool
        - pool_size: Number of connections to maintain (5 for moderate load)
        - pool_reset_session: Reset session variables on connection return
        """
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="automation_pool",
                pool_size=5,  # Adjust based on concurrent script needs
                pool_reset_session=True,
                **self._config
            )
            logger.info(f"✓ Connection pool created (size: 5)")
        except Error as e:
            logger.error(f"✗ Failed to create connection pool: {e}")
            raise
    
    def get_connection(self):
        """
        Get a connection from the pool.
        
        Returns:
            mysql.connector.connection.MySQLConnection: Database connection
            
        Raises:
            Error: If connection cannot be established
        """
        try:
            connection = self._pool.get_connection()
            
            if connection.is_connected():
                logger.debug("✓ Connection acquired from pool")
                return connection
            else:
                logger.warning("⚠ Connection not active, reconnecting...")
                connection.reconnect(attempts=3, delay=1)
                return connection
                
        except Error as e:
            logger.error(f"✗ Failed to get connection from pool: {e}")
            raise
    
    @contextmanager
    def get_cursor(self, dictionary=False, buffered=True):
        """
        Context manager for safe cursor operations.
        
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                results = cursor.fetchall()
        
        Args:
            dictionary: Return rows as dictionaries (default: False)
            buffered: Use buffered cursor (default: True)
            
        Yields:
            mysql.connector.cursor.MySQLCursor: Database cursor
        """
        connection = None
        cursor = None
        
        try:
            connection = self.get_connection()
            cursor = connection.cursor(dictionary=dictionary, buffered=buffered)
            yield cursor
            connection.commit()  # Auto-commit on success
            
        except Error as e:
            if connection:
                connection.rollback()  # Auto-rollback on error
            logger.error(f"✗ Database operation failed: {e}")
            raise
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()  # Return to pool
                logger.debug("✓ Connection returned to pool")
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True) -> Optional[list]:
        """
        Execute a single query with automatic connection management.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            fetch: Whether to fetch results (default: True)
            
        Returns:
            List of results if fetch=True, None otherwise
            
        Raises:
            Error: If query execution fails
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            
            if fetch:
                return cursor.fetchall()
            return None
    
    def execute_many(self, query: str, data: list) -> int:
        """
        Execute query with multiple parameter sets (bulk insert/update).
        
        Args:
            query: SQL query with placeholders
            data: List of parameter tuples
            
        Returns:
            Number of affected rows
            
        Raises:
            Error: If execution fails
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, data)
            return cursor.rowcount
    
    def test_connection(self) -> bool:
        """
        Test database connectivity.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            with self.get_cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    logger.info("✓ Database connection test successful")
                    return True
                    
        except Error as e:
            logger.error(f"✗ Database connection test failed: {e}")
            return False
        
        return False
    
    def get_server_info(self) -> Dict[str, str]:
        """
        Get database server information.
        
        Returns:
            Dict containing server version and connection details
        """
        try:
            connection = self.get_connection()
            info = {
                'server_version': connection.get_server_info(),
                'database': self._config['database'],
                'host': self._config['host'],
                'port': self._config['port'],
                'user': self._config['user']
            }
            connection.close()
            return info
            
        except Error as e:
            logger.error(f"✗ Failed to get server info: {e}")
            return {}
    
    def close_pool(self) -> None:
        """
        Close all connections in the pool.
        Use this only when shutting down the application.
        """
        if self._pool:
            # Note: mysql.connector.pooling doesn't have a direct close_all method
            # Connections are closed when they're garbage collected
            logger.info("✓ Connection pool shutdown initiated")
            self._pool = None


# Global instance (singleton)
db_connection = DatabaseConnection()


# Convenience functions for backward compatibility
def get_connection():
    """Get a database connection from the pool"""
    return db_connection.get_connection()


def get_cursor(dictionary=False, buffered=True):
    """Get a cursor context manager"""
    return db_connection.get_cursor(dictionary=dictionary, buffered=buffered)


def execute_query(query: str, params: tuple = None, fetch: bool = True):
    """Execute a single query"""
    return db_connection.execute_query(query, params, fetch)


def execute_many(query: str, data: list):
    """Execute bulk operations"""
    return db_connection.execute_many(query, data)


def test_connection():
    """Test database connectivity"""
    return db_connection.test_connection()


def get_server_info():
    """Get server information"""
    return db_connection.get_server_info()


# Module-level test
if __name__ == "__main__":
    # Configure logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "=" * 70)
    print("  DATABASE CONNECTION TEST")
    print("=" * 70 + "\n")
    
    try:
        # Test connection
        if test_connection():
            print("✓ Connection test PASSED\n")
            
            # Show server info
            info = get_server_info()
            print("Server Information:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            print("\n" + "=" * 70)
            print("  ALL TESTS PASSED")
            print("=" * 70 + "\n")
        else:
            print("✗ Connection test FAILED\n")
            
    except Exception as e:
        print(f"✗ Error during testing: {e}\n")
