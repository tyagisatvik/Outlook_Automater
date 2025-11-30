"""Celery worker entry point"""
from app.tasks.celery_app import celery_app

# This file is used to start the Celery worker
# Usage: celery -A celery_worker worker --loglevel=info

if __name__ == "__main__":
    celery_app.start()
