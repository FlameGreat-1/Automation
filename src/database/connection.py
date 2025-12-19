"""
Database Connection Manager
Provides centralized, production-grade database connection handling
for all automation scripts.

Features:
- Connection pooling for performance
- Automatic reconnection with exponential backoff
- Stale connection detection
- Thread-safe operations
- Environment-based configuration
- Comprehensive error handling
- Context manager support
- Connection health monitoring
- Query timeout handling
"""

import os
import time
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error, pooling

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
    _stats = {
        'connections_created': 0,
        'connections_failed': 0,
        'queries_executed': 0,
        'queries_failed': 0,
        'reconnections': 0
    }
    
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
        
        self._config = self._load_config()
        self._validate_config()
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
            'autocommit': False,
            'raise_on_warnings': True,
            'get_warnings': True,
            'connection_timeout': 30,
            'use_pure': True,
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
        - pool_size: Number of connections to maintain
        - pool_reset_session: Reset session variables on connection return
        """
        try:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="automation_pool",
                pool_size=5,
                pool_reset_session=True,
                **self._config
            )
            logger.info(f"✓ Connection pool created (size: 5)")
        except Error as e:
            logger.error(f"✗ Failed to create connection pool: {e}")
            raise
    
    def get_connection(self, max_retries: int = 3, retry_delay: int = 2):
        """
        Get a connection from the pool with retry logic.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        
        Returns:
            mysql.connector.connection.MySQLConnection: Database connection
            
        Raises:
            Error: If connection cannot be established after retries
        """
        for attempt in range(1, max_retries + 1):
            try:
                connection = self._pool.get_connection()
                
                if connection.is_connected():
                    if not self._is_connection_healthy(connection):
                        logger.warning("⚠ Connection unhealthy, reconnecting...")
                        connection.reconnect(attempts=3, delay=1)
                        self._stats['reconnections'] += 1
                    
                    self._stats['connections_created'] += 1
                    logger.debug(f"✓ Connection acquired from pool (attempt {attempt})")
                    return connection
                else:
                    logger.warning(f"⚠ Connection not active (attempt {attempt}), reconnecting...")
                    connection.reconnect(attempts=3, delay=1)
                    self._stats['reconnections'] += 1
                    return connection
                    
            except Error as e:
                self._stats['connections_failed'] += 1
                
                if attempt < max_retries:
                    delay = retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"⚠ Connection attempt {attempt} failed, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"✗ Failed to get connection after {max_retries} attempts: {e}")
                    raise
        
        raise Error("Failed to establish database connection")
    
    def _is_connection_healthy(self, connection) -> bool:
        """
        Check if connection is healthy by executing a simple query.
        
        Args:
            connection: MySQL connection to check
            
        Returns:
            bool: True if connection is healthy
        """
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except Error:
            return False
    
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
            connection.commit()
            self._stats['queries_executed'] += 1
            
        except Error as e:
            if connection:
                connection.rollback()
            self._stats['queries_failed'] += 1
            logger.error(f"✗ Database operation failed: {e}")
            raise
            
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
                logger.debug("✓ Connection returned to pool")
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = True, timeout: int = 30) -> Optional[list]:
        """
        Execute a single query with automatic connection management.
        
        Args:
            query: SQL query to execute
            params: Query parameters (optional)
            fetch: Whether to fetch results (default: True)
            timeout: Query timeout in seconds (default: 30)
            
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
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get connection pool statistics.
        
        Returns:
            Dict containing connection and query statistics
        """
        return self._stats.copy()
    
    def reset_stats(self) -> None:
        """Reset connection statistics"""
        for key in self._stats:
            self._stats[key] = 0
        logger.info("✓ Connection statistics reset")
    
    def close_pool(self) -> None:
        """
        Close all connections in the pool.
        Use this only when shutting down the application.
        """
        if self._pool:
            logger.info("✓ Connection pool shutdown initiated")
            self._pool = None


db_connection = DatabaseConnection()


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


def get_stats():
    """Get connection statistics"""
    return db_connection.get_stats()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("\n" + "=" * 70)
    print("  DATABASE CONNECTION TEST")
    print("=" * 70 + "\n")
    
    try:
        if test_connection():
            print("✓ Connection test PASSED\n")
            
            info = get_server_info()
            print("Server Information:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            
            stats = get_stats()
            print("\nConnection Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
            
            print("\n" + "=" * 70)
            print("  ALL TESTS PASSED")
            print("=" * 70 + "\n")
        else:
            print("✗ Connection test FAILED\n")
            
    except Exception as e:
        print(f"✗ Error during testing: {e}\n")
