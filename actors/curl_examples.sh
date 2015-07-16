
# Some simple examples exercising the APIs with curl
curl localhost:5000/actors
curl -X POST --data "name=foo&image=busybox" localhost:5000/actors
curl -X POST --data "name=bar&image=bar_image&description=The bar actor" localhost:5000/actors
curl -X POST --data "name=foo&image=busybox&description=A second foo actor" localhost:5000/actors
curl localhost:5000/actors/foo_0
curl localhost:5001/actors/foo_0/messages
curl -X POST --data "message=Go!" localhost:5001/actors/foo_0/messages
curl localhost:5000/actors/foo_0/state
curl -X POST --data "state=some state" localhost:5000/actors/foo_0/state
curl localhost:5000/actors/foo_0/state
curl localhost:5000/actors/foo_0/executions
curl -X POST --data "cpu=31&io=114&runtime=8256" localhost:5000/actors/foo_0/executions
curl -X POST --data "cpu=9&io=5&runtime=1000" localhost:5000/actors/foo_0/executions
curl localhost:5000/actors/foo_0/executions
curl -X DELETE localhost:5000/actors/foo_1