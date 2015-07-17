
# Some simple examples exercising the APIs with curl
curl localhost:5000/actors
curl -X POST --data "name=foo&image=jstubbs/abaco_test" localhost:5000/actors
curl -X POST --data "name=bar&image=bar_image&description=The bar actor" localhost:5000/actors
curl -X POST --data "name=foo&image=busybox&description=A second foo actor" localhost:5000/actors
curl localhost:5000/actors/foo_0
curl localhost:5001/actors/foo_0/messages
curl -X POST --data "message=testing execution" localhost:5001/actors/foo_0/messages
curl localhost:5000/actors/foo_0/state
curl -X POST --data "state=some state" localhost:5000/actors/foo_0/state
curl localhost:5000/actors/foo_0/state
curl localhost:5000/actors/foo_0/executions
curl -X POST --data "cpu=31&io=114&runtime=8256" localhost:5000/actors/foo_0/executions
curl -X POST --data "cpu=9&io=5&runtime=1000" localhost:5000/actors/foo_0/executions
curl localhost:5000/actors/foo_0/executions
curl -X DELETE localhost:5000/actors/foo_1





# add, message, and update example

curl -X POST --data "name=foo&image=jstubbs/abaco_test" localhost:5000/actors
curl -X POST --data "name=foo&image=jstubbs/abaco_test_nosleep" localhost:5000/actors
curl localhost:5000/actors/foo_0
curl -X POST --data "message=testing execution" localhost:5001/actors/foo_0/messages
curl -X PUT --data "name=foo&image=jstubbs/abaco_test2" localhost:5000/actors/foo_0