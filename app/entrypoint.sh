#!/bin/bash
set -e

if [ "$CELERY" = "1" ]; then
    exec celery -A app.worker worker --loglevel=INFO --concurrency 1 -B \
         --schedule-filename /tmp/celerybeat-schedule \
         --queues "$CELERY_QUEUE"
else
    FLASK_APP=app flask db upgrade
    exec gunicorn --bind 0.0.0.0:5000 \
        -w "${GUNICORN_WORKERS:-8}" \
        --statsd-host statsd:8125 \
        --statsd-prefix tenant \
        "app:create_app()"
fi
