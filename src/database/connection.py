"""Database connection management with connection pooling."""

import structlog
from contextlib import contextmanager
from typing import Optional, Generator, Any
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import DatabaseConfig, load_config

logger = structlog.get_logger(__name__)

# Try psycopg2 first, fall back to pg8000
USE_PSYCOPG2 = False
pool = None
RealDictCursor = None

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    # Test that it actually works by accessing the version
    _ = psycopg2.__version__
    USE_PSYCOPG2 = True
except Exception:
    # Any error means psycopg2 isn't working - use pg8000
    USE_PSYCOPG2 = False

if not USE_PSYCOPG2:
    import pg8000
    import pg8000.native

# Global connection pool (psycopg2 only)
_connection_pool = None
# Global connection for pg8000
_pg8000_connection = None


class DatabaseConnection:
    """Database connection manager with connection pooling."""

    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or load_config().database
        self._ensure_connection()

    def _ensure_connection(self) -> None:
        """Ensure connection/pool exists."""
        global _connection_pool, _pg8000_connection

        if USE_PSYCOPG2:
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
        else:
            if _pg8000_connection is None:
                _pg8000_connection = pg8000.connect(
                    host=self.config.host,
                    port=int(self.config.port),
                    database=self.config.name,
                    user=self.config.user,
                    password=self.config.password,
                )
                logger.info("database_connection_created", host=self.config.host, database=self.config.name)

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a connection from the pool."""
        global _connection_pool, _pg8000_connection
        conn = None
        try:
            if USE_PSYCOPG2:
                conn = _connection_pool.getconn()
                yield conn
            else:
                yield _pg8000_connection
        except Exception as e:
            logger.error("database_connection_error", error=str(e))
            raise
        finally:
            if USE_PSYCOPG2 and conn:
                _connection_pool.putconn(conn)

    @contextmanager
    def get_cursor(self, commit: bool = True) -> Generator[Any, None, None]:
        """Get a cursor with automatic commit/rollback."""
        with self.get_connection() as conn:
            if USE_PSYCOPG2:
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cursor = conn.cursor()
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

    def _rows_to_dicts(self, cursor, rows) -> list:
        """Convert rows to dictionaries for pg8000."""
        if USE_PSYCOPG2:
            return rows  # Already dicts with RealDictCursor
        if not rows:
            return []
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def _row_to_dict(self, cursor, row) -> Optional[dict]:
        """Convert single row to dictionary for pg8000."""
        if USE_PSYCOPG2:
            return row  # Already dict with RealDictCursor
        if not row:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute(self, query: str, params: tuple = None, fetch: bool = False) -> Optional[list]:
        """Execute a query with retry logic."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                rows = cursor.fetchall()
                return self._rows_to_dicts(cursor, rows)
            return None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def execute_one(self, query: str, params: tuple = None) -> Optional[dict]:
        """Execute a query and fetch one result."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return self._row_to_dict(cursor, row)

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
    global _connection_pool, _pg8000_connection
    if USE_PSYCOPG2 and _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("database_pool_closed")
    elif not USE_PSYCOPG2 and _pg8000_connection:
        _pg8000_connection.close()
        _pg8000_connection = None
        logger.info("database_connection_closed")
