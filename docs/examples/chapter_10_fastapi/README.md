# FastAPI + ClickHouse + Async Backend Example
# docs/examples/chapter_10_fastapi/README.md

This example demonstrates request-level connection management in FastAPI async applications.

## Core Principle

**"Connect on demand, disconnect after use"** - Each HTTP request creates an independent `AsyncBackendGroup` instance and manages its connection lifecycle.

## Why This Approach?

### ClickHouse's Limitation
- `clickhouse-connector-python` has `threadsafety=1`
- Connection pool is NOT suitable
- Connections cannot be shared across threads

### Request-Level Isolation
- Each request gets its own `AsyncBackendGroup`
- No race conditions between requests
- Automatic cleanup on request completion

## File Structure

```
chapter_10_fastapi/
├── README.md           # This file
├── config_loader.py    # Database configuration
├── models.py           # Async model definitions
├── database.py         # Request-level connection manager
└── app.py              # FastAPI application
```

## Key Components

### 1. Request-Level BackendGroup (`database.py`)

```python
@asynccontextmanager
async def get_request_db():
    # Create request-level BackendGroup (request isolation)
    group = AsyncBackendGroup(
        name="request",
        models=[AsyncUser, AsyncPost, AsyncComment],
        config=config,
        backend_class=AsyncClickHouseBackend
    )
    
    try:
        await group.configure()
        backend = group.get_backend()
        
        # Use context() for connection lifecycle
        async with backend.context():
            yield backend
    
    finally:
        await group.disconnect()
```

### 2. Dependency Injection (`app.py`)

```python
@app.get("/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_request_db)):
    user = await AsyncUser.find_one(user_id)
    return {"user": user.to_dict()}
```

## Running

```bash
cd docs/examples/chapter_10_fastapi
uvicorn app:app --reload
```

## Testing

```bash
# List users
curl http://localhost:8000/users

# Create user
curl -X POST http://localhost:8000/users \
     -H "Content-Type: application/json" \
     -d '{"username": "test", "email": "test@example.com"}'

# Get user
curl http://localhost:8000/users/1

# Get user's posts
curl http://localhost:8000/users/1/posts

# Create post
curl -X POST http://localhost:8000/posts \
     -H "Content-Type: application/json" \
     -d '{"user_id": 1, "title": "My First Post", "body": "Hello World"}'

# Add comment
curl -X POST http://localhost:8000/posts/1/comments \
     -H "Content-Type: application/json" \
     -d '{"user_id": 1, "body": "Great post!"}'
```

## Use Cases

### Suitable
- Web API applications
- Lightweight query scenarios
- CRUD operations
- Short-lived HTTP requests

### Not Suitable
- WebSocket long connections (consider connection pool)
- Batch processing (consider multiprocessing)
- Heavy computation (consider multiprocessing)

## Performance

- Each request has connection create/disconnect overhead
- Overhead is acceptable for typical web workloads
- For high-concurrency scenarios, consider PostgreSQL with `BackendPool`
