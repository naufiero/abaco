=====
abaco
=====

Actor Based Co(ntainers)mputing

Intro
=====
abaco is a REST-ful API platform for the actor model of concurrent computation
where each actor is associated with a Linux (for now, docker) container. Actor
containers are executed in response to messages posted to their inbox. In the
process, state, logs and execution statistics are collected. Many aspects of the
system are configurable.


Quickstart
==========
1. Deploy a development version of the abaco stack using docker-compose. From within
the project root execute:

      .. code-block:: bash
      $ docker-compose up -d

The services are now running behind nginx which should be listenting on 8000.


2. Register an actor -- To define an actor, pass a name and an image available
on the public docker hub.

    .. code-block:: bash
    $ curl -X POST --data "image=jstubbs/abaco_test&name=foo" "localhost:8000/actors"

abaco responds in json; you should see something like this:

    .. code-block:: bash
    {
        "status": "success",
        "msg": "Actor created successfully.",
        "result": {
            "description": null,
            "executions": {},
            "id": "foo_0",
            "image": "jstubbs/abaco_test",.
            "name": "foo",
            "state": "",
            "status": "SUBMITTED",
        },
        "version": "0.01"
    }

3. Notice that abaco returned a status of `SUBMITTED`; behind the scences, abaco
is starting two worker containers to handle messages passed to this actor. The workers
must initialize themselves (download the image, etc) before the actor is ready. You can
retrieve the details about an actor (including the status) by making a GET request to
a specific actor like:

    .. code-block:: bash
    $ curl localhost:8000/actors/foo_0

When the actor's workers are initialized, you will see a response like this:

    .. code-block:: bash
    {
        "msg": "Actor retrieved successfully.",
        "result": {
            "description": null,
            "executions": {},
            "id": "foo_0",
            "image": "jstubbs/abaco_test",
            "name": "foo",
            "state": "",
            "status": "READY",
            "subscriptions": []
        },
        "status": "success",
        "version": "0.01"
    }

4. We're now ready to execute our actor. To do so, make a POST request to the messages endpoint, passing a message string as the payload.

.. code-block:: bash
    $ curl -X POST --data "message=execute yourself"  localhost:8000/actors/foo_0/message

abaco executes the image resigtered for foo_0, in this case, jstubbs/abaco_test, and passes in the string `execute yourself` as an environmental variable ($MSG). abaco will use the default command included in the image when executing the container. The response will look like this:

    .. code-block:: bash
    {
        "msg": "The request was successful",
        "result": {
            "msg": "execute yourself"
        },
        "status": "success",
        "version": "0.01"
    }

5. The abaco_test image simply echo's the environment and does a sleep for 5 seconds. Once the container finishes an execution is registered for the actor with some basic statistics:

    .. code-block:: bash
    $ curl localhost:8000/actors/foo_0/executions

The response will look something like:

    .. code-block:: bash

    {
        "msg": "Actor executions retrieved successfully.",
        "result": {
            "ids": [
                "foo_0_exc_0"
            ],
            "total_cpu": 65599470,
            "total_executions": 1,
            "total_io": 1021,
            "total_runtime": 2
        },
        "status": "success",
        "version": "0.01"
    }

6. You can also retrieve the logs for any execution:

    .. code-block:: bash
    $ curl localhost:8000/actors/foo_0/executions/foo_0_exc_0/logs

Response:

    .. code-block:: bash

    {
        "msg": "Logs retrieved successfully.",
        "result": "Contents of MSG: execute yourself\nEnvironment:\nHOSTNAME=6310620f644a\nSHLVL=1\nHOME=/root\nMSG=execute yourself\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nPWD=/\n",
        "status": "success",
        "version": "0.01"
    }

