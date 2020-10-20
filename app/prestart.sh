#! /usr/bin/env bash
# This file starts before the entry point of the container
# Let the DB start
# sleep 10;
# Run migrations

FLASK_APP=main flask db upgrade

celery -A main.celery worker --loglevel=INFO &
