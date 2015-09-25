#!/bin/bash
docker run -d -v /var/run/docker.sock:/var/run/docker.sock -v $(pwd)/abaco-staging.conf:/etc/abaco.conf -e AE_IMAGE=jstubbs/abaco_core jstubbs/abaco_core python3 -u /actors/spawner.py