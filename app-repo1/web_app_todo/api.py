import os
import time
import bcrypt

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

import db


app = FastAPI(title="todo-app-api", version="1.0.0")


# -----------------------------
# DB init on startup
# -----------------------------
@app.on_event("startup")
def startup_event():
    db.init_db()


# -----------------------------
# Request models
# -----------------------------
class SignupRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)


class TodoCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=500)


# -----------------------------
# Helpers
# -----------------------------
def get_user_or_404(username: str):
    user = db.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -----------------------------
# Health endpoints
# -----------------------------
@app.get("/livez")
def livez():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    ok = db.db_healthcheck()
    if not ok:
        raise HTTPException(status_code=503, detail="db not ready")
    return {"status": "ok"}


# -----------------------------
# Auth endpoints
# -----------------------------
@app.post("/api/signup")
def signup(req: SignupRequest):
    existing_user = db.get_user(req.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")

    pw_hash = bcrypt.hashpw(
        req.password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    ok = db.create_user(req.username, pw_hash)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to create user")

    user = db.get_user(req.username)
    return {
        "message": "User created successfully",
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
    }


@app.post("/api/login")
def login(req: LoginRequest):
    user = db.get_user(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not bcrypt.checkpw(
        req.password.encode("utf-8"),
        user["password_hash"].encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    db.touch_user_last_seen(user["id"])

    return {
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
    }


# -----------------------------
# Todo endpoints
# -----------------------------
@app.get("/api/todos")
def get_todos(username: str = Query(..., min_length=1)):
    user = get_user_or_404(username)
    db.touch_user_last_seen(user["id"])
    todos = db.list_todos(user["id"])
    return {
        "user": {
            "id": user["id"],
            "username": user["username"],
        },
        "count": len(todos),
        "todos": todos,
    }


@app.post("/api/todos")
def create_todo(req: TodoCreateRequest):
    user = get_user_or_404(req.username)
    db.touch_user_last_seen(user["id"])

    db.add_todo(user["id"], req.title)

    todos = db.list_todos(user["id"])
    latest_todo = todos[0] if todos else None

    return {
        "message": "Todo created successfully",
        "todo": latest_todo,
        "count": len(todos),
    }


@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: int, username: str = Query(..., min_length=1)):
    user = get_user_or_404(username)
    db.touch_user_last_seen(user["id"])

    existing_todos = db.list_todos(user["id"])
    existing_ids = {todo["id"] for todo in existing_todos}
    if todo_id not in existing_ids:
        raise HTTPException(status_code=404, detail="Todo not found")

    db.delete_todo(user["id"], todo_id)

    remaining_todos = db.list_todos(user["id"])
    return {
        "message": "Todo deleted successfully",
        "count": len(remaining_todos),
        "todos": remaining_todos,
    }