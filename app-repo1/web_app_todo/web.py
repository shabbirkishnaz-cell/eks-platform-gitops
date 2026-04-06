import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import streamlit as st
import bcrypt

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    CollectorRegistry,
    start_http_server,
)

import db

# -----------------------------
# App identity labels
# -----------------------------
APP_NAME = os.getenv("APP_NAME", "todo-app")
APP_ENV = os.getenv("APP_ENV", "prod")
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

K8S_NAMESPACE = os.getenv("POD_NAMESPACE", "unknown")
K8S_POD = os.getenv("POD_NAME", "unknown")
K8S_NODE = os.getenv("NODE_NAME", "unknown")


def _lbl():
    # order must match labelnames below
    return (APP_NAME, APP_ENV, APP_VERSION, K8S_NAMESPACE, K8S_POD)


# -----------------------------
# Prometheus (safe for Streamlit reruns)
# -----------------------------
@st.cache_resource
def _metrics():
    registry = CollectorRegistry()

    build_info = Info(
        "todo_app_build_info",
        "Build and runtime information",
        registry=registry,
    )
    build_info.info(
        {
            "app": APP_NAME,
            "env": APP_ENV,
            "version": APP_VERSION,
            "namespace": K8S_NAMESPACE,
            "pod": K8S_POD,
            "node": K8S_NODE,
        }
    )

    requests_total = Counter(
        "todo_app_requests_total",
        "Total todo-app operations",
        ["action", "app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    errors_total = Counter(
        "todo_app_errors_total",
        "Total todo-app errors",
        ["type", "app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    todos_total = Gauge(
        "todo_app_todos_total",
        "Total number of todos across all users (global DB total)",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    todos_count_current_user = Gauge(
        "todo_app_todos_count_current_user",
        "Current user's todo count (demo metric)",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    users_total = Gauge(
        "todo_app_users_total",
        "Total registered users",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    active_users_5m = Gauge(
        "todo_app_active_users_5m",
        "Active users in last 5 minutes",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    logins_total = Counter(
        "todo_app_logins_total",
        "Total successful logins",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    signups_total = Counter(
        "todo_app_signups_total",
        "Total successful signups",
        ["app", "env", "version", "namespace", "pod"],
        registry=registry,
    )

    request_latency_seconds = Histogram(
        "todo_app_request_latency_seconds",
        "Latency of todo-app actions in seconds (histogram)",
        ["action", "app", "env", "version", "namespace", "pod"],
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        registry=registry,
    )

    return {
        "registry": registry,
        "REQUESTS_TOTAL": requests_total,
        "ERRORS_TOTAL": errors_total,
        "TODOS_TOTAL": todos_total,
        "TODOS_COUNT_CURRENT_USER": todos_count_current_user,
        "USERS_TOTAL": users_total,
        "ACTIVE_USERS_5M": active_users_5m,
        "LOGINS_TOTAL": logins_total,
        "SIGNUPS_TOTAL": signups_total,
        "REQUEST_LATENCY_SECONDS": request_latency_seconds,
    }


@st.cache_resource
def _start_metrics_server():
    m = _metrics()
    start_http_server(8000, registry=m["registry"])
    return True


_start_metrics_server()


# -----------------------------
# DB init (once)
# -----------------------------
@st.cache_resource
def _init_db_once():
    db.init_db()
    return True


_init_db_once()

M = _metrics()
REQUESTS_TOTAL = M["REQUESTS_TOTAL"]
ERRORS_TOTAL = M["ERRORS_TOTAL"]
TODOS_TOTAL = M["TODOS_TOTAL"]
TODOS_COUNT_CURRENT_USER = M["TODOS_COUNT_CURRENT_USER"]
USERS_TOTAL = M["USERS_TOTAL"]
ACTIVE_USERS_5M = M["ACTIVE_USERS_5M"]
LOGINS_TOTAL = M["LOGINS_TOTAL"]
SIGNUPS_TOTAL = M["SIGNUPS_TOTAL"]
REQUEST_LATENCY_SECONDS = M["REQUEST_LATENCY_SECONDS"]


# -----------------------------
# Health server for probes (:8081)
# -----------------------------
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/livez":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if self.path == "/healthz":
            ok = db.db_healthcheck()
            if ok:
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ok")
            else:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b"db not ready")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, fmt, *args):
        # keep logs clean
        return


@st.cache_resource
def _start_health_server():
    def run():
        httpd = HTTPServer(("0.0.0.0", 8081), HealthHandler)
        httpd.serve_forever()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return True


_start_health_server()


# -----------------------------
# Helpers
# -----------------------------
def set_user_session(user):
    st.session_state["user_id"] = user["id"]
    st.session_state["username"] = user["username"]


def logout():
    st.session_state.pop("user_id", None)
    st.session_state.pop("username", None)
    st.rerun()


def refresh_global_user_metrics():
    try:
        USERS_TOTAL.labels(*_lbl()).set(db.users_total_count())
        ACTIVE_USERS_5M.labels(*_lbl()).set(db.active_users_count(5))
    except Exception:
        ERRORS_TOTAL.labels("db", *_lbl()).inc()


# -----------------------------
# UI
# -----------------------------
def signup_ui():
    st.subheader("Sign up")
    username = st.text_input("Username", key="signup_user")
    password = st.text_input("Password", type="password", key="signup_pass")

    if st.button("Create account"):
        start = time.perf_counter()
        try:
            REQUESTS_TOTAL.labels("signup", *_lbl()).inc()

            if not username or not password:
                st.error("Username and password are required.")
                return

            pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            ok = db.create_user(username, pw_hash)
            if not ok:
                st.error("Username already exists. Try logging in.")
                return

            SIGNUPS_TOTAL.labels(*_lbl()).inc()
            refresh_global_user_metrics()
            st.success("Account created. Please log in.")
        except Exception:
            ERRORS_TOTAL.labels("signup", *_lbl()).inc()
            st.error("Signup failed.")
        finally:
            REQUEST_LATENCY_SECONDS.labels("signup", *_lbl()).observe(time.perf_counter() - start)


def login_ui():
    st.subheader("Log in")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Log in"):
        start = time.perf_counter()
        try:
            REQUESTS_TOTAL.labels("login", *_lbl()).inc()

            user = db.get_user(username)
            if not user:
                st.error("User not found. Please sign up first.")
                return

            ok = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8"))
            if not ok:
                st.error("Wrong password.")
                return

            # mark active user
            db.touch_user_last_seen(user["id"])
            LOGINS_TOTAL.labels(*_lbl()).inc()
            refresh_global_user_metrics()

            set_user_session(user)
            st.rerun()
        except Exception:
            ERRORS_TOTAL.labels("login", *_lbl()).inc()
            st.error("Login failed.")
        finally:
            REQUEST_LATENCY_SECONDS.labels("login", *_lbl()).observe(time.perf_counter() - start)


def todo_ui():
    st.title(f"My Todo App — {st.session_state['username']}")
    st.caption(f"env={APP_ENV} version={APP_VERSION} | metrics on :8000/metrics")

    if st.button("Logout"):
        logout()

    user_id = st.session_state["user_id"]

    # mark user active each render (good enough for demo)
    try:
        db.touch_user_last_seen(user_id)
    except Exception:
        ERRORS_TOTAL.labels("db", *_lbl()).inc()

    refresh_global_user_metrics()

    # list todos
    try:
        todos = db.list_todos(user_id)
    except Exception:
        ERRORS_TOTAL.labels("db", *_lbl()).inc()
        st.error("DB error while loading todos.")
        return

    # global + per-user counts
    try:
        TODOS_TOTAL.labels(*_lbl()).set(db.todos_total_count())
        TODOS_COUNT_CURRENT_USER.labels(*_lbl()).set(db.todos_count(user_id))
    except Exception:
        ERRORS_TOTAL.labels("db", *_lbl()).inc()

    def refresh_counts():
        try:
            TODOS_TOTAL.labels(*_lbl()).set(db.todos_total_count())
            TODOS_COUNT_CURRENT_USER.labels(*_lbl()).set(db.todos_count(user_id))
            refresh_global_user_metrics()
        except Exception:
            ERRORS_TOTAL.labels("db", *_lbl()).inc()

    def add_todo():
        start = time.perf_counter()
        title = st.session_state.get("new_todo", "").strip()
        if not title:
            return
        try:
            REQUESTS_TOTAL.labels("add_todo", *_lbl()).inc()
            db.add_todo(user_id, title)
            db.touch_user_last_seen(user_id)
            st.session_state["new_todo"] = ""
            refresh_counts()
        except Exception:
            ERRORS_TOTAL.labels("db", *_lbl()).inc()
            st.error("DB error while adding todo.")
        finally:
            REQUEST_LATENCY_SECONDS.labels("add_todo", *_lbl()).observe(time.perf_counter() - start)

    st.text_input(
        label="",
        placeholder="Add a new todo...",
        on_change=add_todo,
        key="new_todo",
    )

    for t in todos:
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            _ = st.checkbox(t["title"], value=t["done"], key=f"todo-{t['id']}")
        with col2:
            if st.button("Delete", key=f"del-{t['id']}"):
                start = time.perf_counter()
                try:
                    REQUESTS_TOTAL.labels("delete_todo", *_lbl()).inc()
                    db.delete_todo(user_id, t["id"])
                    db.touch_user_last_seen(user_id)
                    refresh_counts()
                    st.rerun()
                except Exception:
                    ERRORS_TOTAL.labels("db", *_lbl()).inc()
                    st.error("DB error while deleting todo.")
                finally:
                    REQUEST_LATENCY_SECONDS.labels("delete_todo", *_lbl()).observe(time.perf_counter() - start)


# -----------------------------
# Main
# -----------------------------
if "user_id" not in st.session_state:
    st.title("Welcome to Todo App")
    tab1, tab2 = st.tabs(["Log in", "Sign up"])
    with tab1:
        login_ui()
    with tab2:
        signup_ui()
else:
    todo_ui()
