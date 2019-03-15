#!/bin/bash
#
# Entrypoint for a health check worker process. Runs every ten minutes

# give initial processes some time to launch
sleep 30
# change this back to 120 when done testing

# main loop runs every 10 minutes
while :
do
    python3 -u /actors/update.py
    # sleep 600
done