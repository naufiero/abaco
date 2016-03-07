#!/bin/bash
#
# Entrypoint for a health check worker process. Runs every ten minutes
while :
do
    python3 -u /actors/health.py
    sleep 600
done