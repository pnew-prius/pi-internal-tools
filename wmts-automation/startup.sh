#!/bin/sh
# App Service (Linux) startup command:  sh startup.sh
exec gunicorn --config gunicorn.conf.py wsgi:app
