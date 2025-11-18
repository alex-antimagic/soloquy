"""
RQ Worker for background job processing
Handles async tasks like lead enrichment, email processing, etc.
"""
import os
import sys
from redis import Redis
from rq import Worker, Queue, Connection

# Ensure the application is in the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db

# Create Flask application
app = create_app(os.getenv('FLASK_ENV', 'production'))

# Redis connection with SSL certificate handling
redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
if redis_url.startswith('rediss://'):
    redis_url += '?ssl_cert_reqs=none'
redis_conn = Redis.from_url(redis_url)

# List of queues to listen on
listen_queues = ['default', 'enrichment', 'high', 'low']

if __name__ == '__main__':
    with app.app_context():
        with Connection(redis_conn):
            worker = Worker(list(map(Queue, listen_queues)))
            print(f"Starting RQ worker listening on queues: {', '.join(listen_queues)}")
            print(f"Redis URL: {redis_url}")
            worker.work()
