"""
Shared extension singletons.
Import from here – never from individual blueprints – to avoid circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from apscheduler.schedulers.background import BackgroundScheduler

# --- SQLAlchemy ORM ---
db = SQLAlchemy()

# --- Flask-Login ---
login_manager = LoginManager()

# --- APScheduler (background jobs: VC deadline checker, anomaly sweep) ---
scheduler = BackgroundScheduler(daemon=True)

# --- Server-Sent Events (SSE) message bus ---
# Maps client_id (str) -> queue.Queue of dicts {"event": str, "data": str}
import queue
import threading

_sse_lock = threading.Lock()
_sse_clients: dict[str, queue.Queue] = {}


def sse_subscribe(client_id: str) -> queue.Queue:
    """Register a new SSE client and return its personal queue."""
    q = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients[client_id] = q
    return q


def sse_unsubscribe(client_id: str):
    """Remove a client from the broadcast map."""
    with _sse_lock:
        _sse_clients.pop(client_id, None)


def sse_broadcast(event: str, data: str):
    """Push a message to every connected SSE client (non-blocking)."""
    with _sse_lock:
        dead = []
        for cid, q in _sse_clients.items():
            try:
                q.put_nowait({"event": event, "data": data})
            except queue.Full:
                dead.append(cid)  # client too slow – evict
        for cid in dead:
            _sse_clients.pop(cid, None)
