"""
Gunicorn configuration file for production deployment.
Run with: gunicorn -c gunicorn.conf.py app:app
"""

import os
import multiprocessing

# Server socket
bind = f"{os.environ.get('HOST', '0.0.0.0')}:{os.environ.get('PORT', '5000')}"
backlog = 2048

# Worker processes
workers = int(os.environ.get('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = os.environ.get('WORKER_CLASS', 'gevent')
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
timeout = 120
keepalive = 5
graceful_timeout = 30

# Process naming
proc_name = 'instagram-story-downloader'

# Logging
accesslog = os.environ.get('ACCESS_LOG', '-')  # '-' means stdout
errorlog = os.environ.get('ERROR_LOG', '-')
loglevel = os.environ.get('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    print("=" * 60)
    print("📸 Instagram Story Downloader - Production Server")
    print("=" * 60)
    print(f"Starting with {workers} workers ({worker_class})")


def on_exit(server):
    """Called just before exiting Gunicorn."""
    print("Server shutting down...")


def worker_int(worker):
    """Called when a worker receives SIGINT or SIGQUIT."""
    print(f"Worker {worker.pid} interrupted")


def worker_abort(worker):
    """Called when a worker receives SIGABRT."""
    print(f"Worker {worker.pid} aborted")
