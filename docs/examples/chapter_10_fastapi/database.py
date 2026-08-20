# database.py - Request-level Connection Management
# docs/examples/chapter_10_fastapi/database.py
"""
Request-level database connection manager.

Core principles:
1. Create independent AsyncBackendGroup instance for each request
2. Use backend.context() to manage connection lifecycle
3. Automatically disconnect when request ends ("connect on demand, disconnect after use")

Design rationale:
- ClickHouse's clickhouse-connector-python has threadsafety=1, connection pool is not suitable
- Each request needs independent database connection to avoid race conditions
- Async backend fits FastAPI's async processing model
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from fastapi import Request
from rhosocial.activerecord.connection import AsyncBackendGroup
from rhosocial.activerecord.backend.impl.clickhouse import AsyncClickHouseBackend

from config_loader import load_config
from models import AsyncUser, AsyncPost, AsyncComment


@asynccontextmanager
async def get_request_db():
    """
    Request-level database connection manager.
    
    Usage:
        @app.get("/users/{user_id}")
        async def get_user(user_id: int, db=Depends(get_request_db)):
            user = await AsyncUser.find_one(user_id)
            return {"user": user.to_dict()}
    
    Mechanism:
    1. Create new AsyncBackendGroup for each call (request isolation)
    2. configure() sets all models to share the same backend instance
    3. backend.context() manages connection lifecycle
    4. async with ensures proper disconnection even on exceptions
    
    Performance considerations:
    - Each request has connection create/disconnect overhead (acceptable)
    - Suitable for lightweight query scenarios
    - Not suitable for WebSocket long connections (consider alternatives)
    """
    config = load_config()
    
    # Create request-level BackendGroup (request isolation)
    group = AsyncBackendGroup(
        name="request",  # Name doesn't matter, new instance per request
        models=[AsyncUser, AsyncPost, AsyncComment],
        config=config,
        backend_class=AsyncClickHouseBackend
    )
    
    try:
        # Configure backend (doesn't connect yet)
        await group.configure()
        
        # Get shared backend instance
        backend = group.get_backend()
        
        # Use context() to manage connection lifecycle
        # "Connect on demand, disconnect after use"
        async with backend.context():
            yield backend
    
    finally:
        # Ensure cleanup
        await group.disconnect()


async def init_database():
    """
    Initialize database tables.
    
    Called at application startup to create necessary tables.
    """
    config = load_config()
    backend = AsyncClickHouseBackend(connection_config=config)
    await backend.connect()
    
    # Create users table
    await backend.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(64) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """)
    
    # Create posts table
    await backend.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            view_count INT NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Create comments table
    await backend.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            post_id INT NOT NULL,
            user_id INT NOT NULL,
            body TEXT,
            is_approved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    await backend.disconnect()
    print("Database tables created successfully.")
