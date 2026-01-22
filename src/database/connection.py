"""Database connection management with connection pooling."""

import structlog
from contextlib import contextmanager
from typing import Optional, Generator, Any
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import DatabaseConfig, load_config

logger = structlog.get_logger(__name__)

# Global connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


class DatabaseConnection:
    """Database connection manager with connection pooling."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or load_config().database
        self._ensure_pool()

    def _ensure_pool(self) -> None:
        """Ensure connection pool exists."""
        global _connection_pool
        if _connection_pool is None:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                host=self.config.host,
                port=self.config.port,
                database=self.config.name,
                user=self.config.user,
                password=self.config.password,
            )
            logger.info("database_pool_created", host=self.config.host, database=self.config.name)

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a connection from the pool."""
        global _connection_pool
        conn = None
        try:
            conn = _connection_pool.getconn()
            yield conn
        except Exception as e:
            logger.error("database_connection_error", error=str(e))
            raise
        finally:
            if conn:
                _connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, commit: bool = True) -> Generator[RealDictCursor, None, None]:
        """Get a cursor with automatic commit/rollback."""
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield cursor
                if commit:
                    conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error("database_query_error", error=str(e))
                raise
            finally:
                cursor.close()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[list]:
        """Execute a query with retry logic."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """Execute a query and fetch one result."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def execute_many(self, query: str, params_list: list) -> None:
        """Execute a query with multiple parameter sets."""
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)

    def init_schema(self, schema_path: str = None) -> None:
        """Initialize database schema from SQL file."""
        import os
        if schema_path is None:
            schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        with self.get_cursor() as cursor:
            cursor.execute(schema_sql)
            logger.info("database_schema_initialized")


def get_connection(config: Optional[DatabaseConfig] = None) -> DatabaseConnection:
    """Get a database connection instance."""
    return DatabaseConnection(config)


def close_pool() -> None:
    """Close the connection pool."""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("database_pool_closed")
