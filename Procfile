web: gunicorn --worker-class eventlet -w 4 --worker-connections 1000 run:app --bind 0.0.0.0:$PORT
worker: python worker.py
release: flask db upgrade
