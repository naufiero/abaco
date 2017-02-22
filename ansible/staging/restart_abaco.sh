#!/bin/bash

# remove containers
docker rm -f `docker ps | grep agaveapidev/abaco_core | awk '{print $1;}'`
docker rm -f `docker ps | grep agaveapidev/abaco_nginx | awk '{print $1;}'`

# start web stack
docker-compose -f dc-web.yml up -d

# start compute
docker-compose -f dc-compute.yml up -d
