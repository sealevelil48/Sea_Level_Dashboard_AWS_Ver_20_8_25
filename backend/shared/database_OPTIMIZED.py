# backend/shared/database_OPTIMIZED.py
"""
Optimized database manager with connection pooling, query caching,
and performance monitoring
"""

import os
import time
import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import contextmanager

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from sqlalchemy import create_engine, pool, event, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool, QueuePool
import pandas as pd

logger = logging.getLogger(__name__)

class OptimizedDatabaseManager:
    """
    Production-ready database manager with:
    - Connection pooling
    - Query result caching
    - Performance monitoring
    - Automatic retry logic
    - Connection health checks
    """
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self.scoped_session = None
        self.redis_client = None
        self.connection_pool_size = 20
        self.max_overflow = 10
        self.pool_timeout = 30
        self.pool_recycle = 3600  # Recycle connections after 1 hour
        self.query_metrics = {
            'total_queries': 0,
            'cache_hits': 0,
            'slow_queries': 0,
            'failed_queries': 0
        }
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Initialize database and cache connections with retry logic"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Database connection with optimized pool settings
                db_url = os.getenv('DATABASE_URL') or os.getenv('DB_URI')
                if not db_url:
                    raise ValueError("DATABASE_URL not configured")
                
                # Configure connection pool based on environment
                if os.getenv('ENV') == 'production':
                    # Production: Use QueuePool for better performance
                    self.engine = create_engine(
                        db_url,
                        poolclass=QueuePool,
                        pool_size=self.connection_pool_size,
                        max_overflow=self.max_overflow,
                        pool_timeout=self.pool_timeout,
                        pool_recycle=self.pool_recycle,
                        pool_pre_ping=True,  # Verify connections before use
                        echo_pool=False,
                        connect_args={
                            'connect_timeout': 10,
                            'application_name': 'sea_level_dashboard',
                            'options': '-c statement_timeout=30000'  # 30 second timeout
                        }
                    )
                else:
                    # Development: Use QueuePool with smaller settings
                    self.engine = create_engine(
                        db_url,
                        poolclass=QueuePool,
                        pool_size=5,
                        max_overflow=5,
                        pool_timeout=10,
                        pool_recycle=1800,
                        pool_pre_ping=True,
                        echo=False
                    )
                
                # Setup session factory with optimized settings
                self.session_factory = sessionmaker(
                    bind=self.engine,
                    autoflush=False,
                    autocommit=False,
                    expire_on_commit=False
                )
                self.scoped_session = scoped_session(self.session_factory)
                
                # Setup Redis cache connection if available
                if REDIS_AVAILABLE:
                    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
                    try:
                        self.redis_client = redis.from_url(
                            redis_url,
                            decode_responses=True,
                            socket_timeout=5,
                            socket_connect_timeout=5,
                            socket_keepalive=True,
                            socket_keepalive_options={
                                1: 1,  # TCP_KEEPIDLE
                                2: 2,  # TCP_KEEPINTVL
                                3: 3,  # TCP_KEEPCNT
                            },
                            health_check_interval=30
                        )
                        # Test Redis connection
                        self.redis_client.ping()
                        logger.info("Redis cache connected successfully")
                    except Exception as e:
                        logger.warning(f"Redis connection failed: {e}")
                        self.redis_client = None
                
                # Add event listeners for monitoring
                self._setup_event_listeners()
                
                # Test connections
                self._test_connections()
                
                logger.info("Database connections initialized successfully")
                break
                
            except Exception as e:
                logger.error(f"Connection initialization failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    # Fallback to basic connection without pooling
                    self._initialize_fallback_connection()
    
    def _initialize_fallback_connection(self):
        """Initialize basic fallback connection without advanced features"""
        try:
            db_url = os.getenv('DATABASE_URL') or os.getenv('DB_URI')
            self.engine = create_engine(db_url, poolclass=NullPool)
            self.session_factory = sessionmaker(bind=self.engine)
            logger.warning("Using fallback database connection without pooling")
        except Exception as e:
            logger.critical(f"Failed to establish fallback connection: {e}")
            raise
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring"""
        
        @event.listens_for(self.engine, "before_execute")
        def receive_before_execute(conn, clauseelement, multiparams, params, execution_options):
            conn.info['query_start_time'] = time.time()
        
        @event.listens_for(self.engine, "after_execute")
        def receive_after_execute(conn, clauseelement, multiparams, params, execution_options, result):
            elapsed = time.time() - conn.info.get('query_start_time', time.time())
            self.query_metrics['total_queries'] += 1
            
            # Log slow queries
            if elapsed > 1.0:  # Queries taking more than 1 second
                self.query_metrics['slow_queries'] += 1
                logger.warning(f"Slow query detected ({elapsed:.2f}s): {str(clauseelement)[:100]}")
    
    def _test_connections(self):
        """Test database and cache connections"""
        # Test database
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        
        # Test Redis if available
        if self.redis_client:
            self.redis_client.ping()
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions with automatic cleanup"""
        session = self.scoped_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            self.query_metrics['failed_queries'] += 1
            logger.error(f"Database session error: {e}")
            raise
        finally:
            session.close()
    
    def _get_cache_key(self, query: str, params: Dict[str, Any]) -> str:
        """Generate cache key for query results"""
        cache_data = f"{query}_{json.dumps(params, sort_keys=True)}"
        return f"query_cache:{hashlib.md5(cache_data.encode()).hexdigest()}"
    
    def _get_from_cache(self, key: str) -> Optional[pd.DataFrame]:
        """Retrieve cached query results"""
        if not self.redis_client:
            return None
        
        try:
            cached = self.redis_client.get(key)
            if cached:
                self.query_metrics['cache_hits'] += 1
                return pd.read_json(cached, orient='records')
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {e}")
        
        return None
    
    def _set_cache(self, key: str, data: pd.DataFrame, ttl: int = 300):
        """Store query results in cache"""
        if not self.redis_client or data.empty:
            return
        
        try:
            json_data = data.to_json(orient='records', date_format='iso')
            self.redis_client.setex(key, ttl, json_data)
        except Exception as e:
            logger.warning(f"Cache storage failed: {e}")
    
    def execute_query_optimized(
        self, 
        query: str, 
        params: Dict[str, Any] = None,
        cache_ttl: int = 300,
        chunk_size: int = 10000
    ) -> pd.DataFrame:
        """
        Execute query with caching and chunked processing
        
        Args:
            query: SQL query to execute
            params: Query parameters
            cache_ttl: Cache time-to-live in seconds
            chunk_size: Size of chunks for large result sets
        
        Returns:
            Query results as DataFrame
        """
        params = params or {}
        
        # Check cache first
        cache_key = self._get_cache_key(query, params)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Execute query with chunked processing
        chunks = []
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), params)
                
                # Process in chunks to manage memory
                while True:
                    chunk = result.fetchmany(chunk_size)
                    if not chunk:
                        break
                    
                    df_chunk = pd.DataFrame(chunk, columns=result.keys())
                    chunks.append(df_chunk)
                    
                    # Allow other operations between chunks
                    if len(chunks) % 10 == 0:
                        logger.info(f"Processed {len(chunks) * chunk_size} rows...")
            
            # Combine chunks
            if chunks:
                df = pd.concat(chunks, ignore_index=True)
                
                # Cache the result
                self._set_cache(cache_key, df, cache_ttl)
                
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            self.query_metrics['failed_queries'] += 1
            logger.error(f"Query execution failed: {e}")
            raise
    
    def bulk_insert_optimized(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        batch_size: int = 1000
    ):
        """
        Optimized bulk insert with batching
        
        Args:
            table_name: Target table name
            data: List of dictionaries to insert
            batch_size: Number of rows per batch
        """
        if not data:
            return
        
        total_rows = len(data)
        inserted = 0
        
        try:
            with self.get_session() as session:
                for i in range(0, total_rows, batch_size):
                    batch = data[i:i + batch_size]
                    
                    # Use bulk_insert_mappings for better performance
                    session.bulk_insert_mappings(
                        table_name,
                        batch
                    )
                    
                    inserted += len(batch)
                    
                    # Commit periodically
                    if inserted % (batch_size * 10) == 0:
                        session.commit()
                        logger.info(f"Inserted {inserted}/{total_rows} rows...")
                
                session.commit()
                logger.info(f"Bulk insert completed: {total_rows} rows")
                
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            raise
    
    def get_connection_pool_status(self) -> Dict[str, Any]:
        """Get current connection pool statistics"""
        if not self.engine or not hasattr(self.engine.pool, 'size'):
            return {'status': 'unavailable'}
        
        try:
            return {
                'size': self.engine.pool.size(),
                'checked_in': self.engine.pool.checkedin(),
                'checked_out': self.engine.pool.checkedout(),
                'overflow': self.engine.pool.overflow(),
                'total': self.engine.pool.size() + self.engine.pool.overflow()
            }
        except Exception as e:
            logger.error(f"Error getting pool status: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get database performance metrics"""
        metrics = {
            **self.query_metrics,
            'cache_hit_rate': (
                self.query_metrics['cache_hits'] / 
                max(1, self.query_metrics['total_queries'])
            ) * 100,
            'connection_pool': self.get_connection_pool_status(),
            'redis_available': self.redis_client is not None
        }
        
        return metrics
    
    def clear_cache(self, pattern: str = None):
        """Clear cache entries"""
        if not self.redis_client:
            return
        
        try:
            if pattern:
                keys = self.redis_client.keys(f"query_cache:{pattern}*")
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # Clear only query cache keys
                keys = self.redis_client.keys("query_cache:*")
                if keys:
                    self.redis_client.delete(*keys)
            
            logger.info(f"Cache cleared: {pattern or 'all query cache'}")
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
    
    def health_check(self) -> bool:
        """Check database connectivity"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()  # Actually fetch the result
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def close(self):
        """Cleanup connections"""
        try:
            if self.engine:
                self.engine.dispose()
            
            if self.redis_client:
                self.redis_client.close()
            
            logger.info("Database connections closed")
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

# Singleton instance
db_manager = OptimizedDatabaseManager()

# Export for use in other modules
__all__ = ['db_manager', 'OptimizedDatabaseManager']