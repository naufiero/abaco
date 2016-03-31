#!/bin/sh

# Some simple examples exercising the APIs with curl
curl localhost:8000/actors
curl -X POST --data "name=foo&image=jstubbs/abaco_test" localhost:8000/actors
curl -X POST --data "name=bar&image=bar_image&description=The bar actor" localhost:8000/actors
curl -X POST --data "name=foo&image=busybox&description=A second foo actor" localhost:8000/actors
curl localhost:8000/actors/foo_0
curl localhost:8000/actors/foo_0/messages
curl -X POST --data "message=testing execution" localhost:8000/actors/foo_0/messages
curl localhost:8000/actors/foo_0/state
curl -X POST --data "state=some state" localhost:8000/actors/foo_0/state
curl localhost:8000/actors/foo_0/state
curl localhost:8000/actors/foo_0/executions
curl -X POST --data "cpu=31&io=114&runtime=8256" localhost:8000/actors/foo_0/executions
curl -X POST --data "cpu=9&io=5&runtime=1000" localhost:8000/actors/foo_0/executions
curl localhost:8000/actors/foo_0/executions
curl -X DELETE localhost:8000/actors/foo_1

# pass json in
curl -X POST -H "Content-Type: application/json" -d '{"image": "jstubbs/abaco_test", "name": "foo", "default_environment":{"key1": "value1"} }' localhost:8000/actors



# add, message, and update example

curl -X POST --data "name=foo&image=jstubbs/abaco_test" localhost:8000/actors
curl -X POST --data "name=foo&image=jstubbs/abaco_test_nosleep" localhost:8000/actors
curl localhost:8000/actors/foo_0
curl -X POST --data "message=testing execution" localhost:5001/actors/foo_0/messages
curl -X PUT --data "name=foo&image=jstubbs/abaco_test2" localhost:8000/actors/foo_0

# register a bunch of actors
for i in {1..20}; do curl -H "X-Jwt-Assertion-AGAVE-PROD: $jwt" -X POST --data "name=test&image=jstubbs/abaco_test" localhost:8000/actors; done

# send off a bunch of messages:
for i in {1..10}; do for j in {1..20}; do curl -H "X-Jwt-Assertion-AGAVE-PROD: $jwt" -X POST --data "message=test_$i_$j" localhost:8000/actors/test_$i/messages; done; done

for i in {1..10}; do for j in {1..20}; do curl -H "X-Jwt-Assertion-AGAVE-PROD: $jwt" -X POST --data "message=test_$i_$j" "$base/actors/test_$i/messages"; done; done

for i in {1..40}; do curl -H "X-Jwt-Assertion-AGAVE-PROD: $jwt" -X POST --data "message=test number $i" localhost:8000/actors/test_0/messages; done