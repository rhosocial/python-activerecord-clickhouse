# app.py - FastAPI Application with ClickHouse Async Backend
# docs/examples/chapter_10_fastapi/app.py
"""
FastAPI application example: Request-level connection management.

This example demonstrates safe usage of ClickHouse async backend in FastAPI.

Run:
    cd docs/examples/chapter_10_fastapi
    uvicorn app:app --reload

Test:
    # List users
    curl http://localhost:8000/users
    
    # Create user
    curl -X POST http://localhost:8000/users \
         -H "Content-Type: application/json" \
         -d '{"username": "test", "email": "test@example.com"}'
    
    # Get single user
    curl http://localhost:8000/users/1
    
    # Get user's posts
    curl http://localhost:8000/users/1/posts
    
    # Create post
    curl -X POST http://localhost:8000/posts \
         -H "Content-Type: application/json" \
         -d '{"user_id": 1, "title": "My First Post", "body": "Hello World"}'
    
    # Get post details
    curl http://localhost:8000/posts/1
    
    # Add comment
    curl -X POST http://localhost:8000/posts/1/comments \
         -H "Content-Type: application/json" \
         -d '{"user_id": 1, "body": "Great post!"}'
"""

from __future__ import annotations

import os
import sys

_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)

from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, EmailStr

from config_loader import load_config
from database import get_request_db, init_database
from models import AsyncUser, AsyncPost, AsyncComment


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas (Request/Response Models)
# ─────────────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool


class PostCreate(BaseModel):
    user_id: int
    title: str
    body: str = ""


class PostResponse(BaseModel):
    id: int
    user_id: int
    title: str
    body: str
    status: str
    view_count: int


class CommentCreate(BaseModel):
    user_id: int
    body: str


class CommentResponse(BaseModel):
    id: int
    post_id: int
    user_id: int
    body: str
    is_approved: bool


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup: Initialize database tables
    await init_database()
    yield
    # Shutdown: No cleanup needed (each request handles its own cleanup)


app = FastAPI(
    title="ClickHouse + FastAPI + Async ActiveRecord Example",
    description="Request-level connection management example",
    version="1.0.0",
    lifespan=lifespan
)


# ─────────────────────────────────────────────────────────────────────────────
# User Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/users", response_model=List[UserResponse])
async def list_users(db=Depends(get_request_db)):
    """List all users."""
    users = await AsyncUser.query().all()
    return [UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        is_active=u.is_active
    ) for u in users]


@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db=Depends(get_request_db)):
    """Create a new user."""
    user = AsyncUser(
        username=user_data.username,
        email=user_data.email,
        is_active=True
    )
    await user.save()
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active
    )


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db=Depends(get_request_db)):
    """Get a single user by ID."""
    user = await AsyncUser.find_one(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active
    )


# ─────────────────────────────────────────────────────────────────────────────
# Post Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(post_data: PostCreate, db=Depends(get_request_db)):
    """Create a new post."""
    # Validate user exists
    user = await AsyncUser.find_one(post_data.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    post = AsyncPost(
        user_id=post_data.user_id,
        title=post_data.title,
        body=post_data.body,
        status="draft"
    )
    await post.save()
    
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        body=post.body,
        status=post.status,
        view_count=post.view_count
    )


@app.get("/posts", response_model=List[PostResponse])
async def list_posts(db=Depends(get_request_db)):
    """List all posts."""
    posts = await AsyncPost.query().all()
    return [PostResponse(
        id=p.id,
        user_id=p.user_id,
        title=p.title,
        body=p.body,
        status=p.status,
        view_count=p.view_count
    ) for p in posts]


@app.get("/posts/{post_id}", response_model=PostResponse)
async def get_post(post_id: int, db=Depends(get_request_db)):
    """Get a single post by ID."""
    post = await AsyncPost.find_one(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        body=post.body,
        status=post.status,
        view_count=post.view_count
    )


@app.get("/users/{user_id}/posts", response_model=List[PostResponse])
async def get_user_posts(user_id: int, db=Depends(get_request_db)):
    """Get all posts by a user."""
    user = await AsyncUser.find_one(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Use relationship query
    posts = await user.posts
    
    return [PostResponse(
        id=p.id,
        user_id=p.user_id,
        title=p.title,
        body=p.body,
        status=p.status,
        view_count=p.view_count
    ) for p in posts]


# ─────────────────────────────────────────────────────────────────────────────
# Comment Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(post_id: int, comment_data: CommentCreate, db=Depends(get_request_db)):
    """Add a comment to a post."""
    # Validate post exists
    post = await AsyncPost.find_one(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Validate user exists
    user = await AsyncUser.find_one(comment_data.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    
    comment = AsyncComment(
        post_id=post_id,
        user_id=comment_data.user_id,
        body=comment_data.body,
        is_approved=False
    )
    await comment.save()
    
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        body=comment.body,
        is_approved=comment.is_approved
    )


@app.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def get_post_comments(post_id: int, db=Depends(get_request_db)):
    """Get all comments for a post."""
    post = await AsyncPost.find_one(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # Use relationship query
    comments = await post.comments
    
    return [CommentResponse(
        id=c.id,
        post_id=c.post_id,
        user_id=c.user_id,
        body=c.body,
        is_approved=c.is_approved
    ) for c in comments]


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
