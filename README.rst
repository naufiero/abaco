=====
abaco
=====

Actor Based Co(ntainers)mputing

Intro
=====

abaco is a web service and distributed system implementing the actor model of concurrent computation
where each actor is associated with a Docker container. Actor
containers are executed in response to messages posted to their inbox. In the
process, state, logs and execution statistics are collected. Many aspects of the
system are configurable.


Quickstart
==========

1. Deploy a development version of the abaco stack using ``docker-compose``. From within
   the project root execute:

   .. code-block:: bash
   
      $ docker-compose -f docker-compose-local.yml up -d

The services are now running behind ``nginx`` which should be listening on 8000.


2. Register an actor -- Initially, the abaco system is empty with no actors defined which can see by making a GET request
   to the root collection:

   .. code-block:: bash

      $ curl localhost:8000/actors

   abaco will respond with a JSON message that looks something like:

      .. code-block:: JSON

            {
                "msg": "Actors retrieved successfully.",
                "result": [],
                "status": "success",
                "version": "0.01"
            }

   To define an actor, pass a name and an image available on the public docker hub.

   .. code-block:: bash
   
      $ curl -X POST --data "image=jstubbs/abaco_test&name=foo" "localhost:8000/actors"

   abaco responds in json; you should see something like this:

   .. code-block:: JSON

        {
            "msg": "Actor created successfully.",
            "result": {
                "default_environment": {},
                "description": "",
                "id": "e68ebbb7-4986-46ee-9332-a1f5cfc6a533",
                "image": "jstubbs/abaco_test",
                "name": "foo",
                "privileged": false,
                "stateless": false,
                "status": "SUBMITTED",
                "tenant": "dev_staging"
            },
            "status": "success",
            "version": "0.01"
        }

   abaco assigned a uuid to the actor (in this case ``e68ebbb7-4986-46ee-9332-a1f5cfc6a533``) and associated with the
   image `jstubbs/abaco_test` which it began pulling from the public Docker hub.

3. Notice that abaco returned a status of ``SUBMITTED`` for the actor; behind the
   scenes, abaco is starting a worker container to handle messages
   passed to this actor. The worker must initialize itself
   (download the image, etc) before the actor is ready. You can
   retrieve the details about an actor (including the status) by
   making a ``GET`` request to a specific actor using its uuid like so:

   .. code-block:: bash

       $ curl localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533

   When the actor's worker is initialized, you will see a response like this:

   .. code-block:: JSON

        {
            "msg": "Actor retrieved successfully.",
            "result": {
                "default_environment": {},
                "description": "",
                "id": "e68ebbb7-4986-46ee-9332-a1f5cfc6a533",
                "image": "jstubbs/abaco_test",
                "name": "test",
                "privileged": false,
                "stateless": false,
                "status": "READY",
                "tenant": "dev_staging"
            },
            "status": "success",
            "version": "0.01"
        }

   A status of "READY" indicates that actor is capable of processing messages by launching containers from the image.


4. We're now ready to execute our actor. To do so, make a ``POST`` request
   to the messages collection for the actor and pass a message string as the payload.

   .. code-block:: bash

      $ curl -X POST --data "message=execute yourself"  localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533/messages

   abaco executes the image registered for ``e68ebbb7-4986-46ee-9332-a1f5cfc6a533``, in this case,
   jstubbs/abaco_test, and passes in the string ``"execute yourself"`` as
   an environmental variable (``$MSG``). abaco will use the default
   command included in the image when executing the container. The
   response will look like this:

   .. code-block:: JSON

        {
            "msg": "The request was successful",
            "result": {
                "msg": "execute yourself"
            },
            "status": "success",
            "version": "0.01"
        }

5. The ``abaco_test`` image simply echo's the environment and does a sleep
   for 5 seconds. Once the container finishes, an execution is
   registered for the actor. An actor's executions can be retrieved using the ``executions`` sub-collection.

   .. code-block:: bash

      $ curl localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533/executions

   The response will include summary statistics of all executions for the actor as well as the id's of each execution:

   .. code-block:: JSON

        {
            "msg": "Actor executions retrieved successfully.",
            "result": {
                "ids": [
                    "27326d48-7f00-4a45-a2f7-76fff8d685e6"
                ],
                "total_cpu": 144132228,
                "total_executions": 1,
                "total_io": 438,
                "total_runtime": 2
            },
            "status": "success",
            "version": "0.01"
        }

   To see details about a specific execution including runtime, cpu, and io usage, make a get
   request using the execution id:

    .. code-block:: bash

      $ curl localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533/executions/27326d48-7f00-4a45-a2f7-76fff8d685e6

   The response will look something like:

    .. code-block:: JSON
        {
            "msg": "Actor execution retrieved successfully.",
            "result": {
                "actor_id": "e68ebbb7-4986-46ee-9332-a1f5cfc6a533",
                "cpu": 144132228,
                "id": "27326d48-7f00-4a45-a2f7-76fff8d685e6",
                "io": 438,
                "runtime": 2,
            },
            "status": "success",
            "version": "0.01"
        }


6. You can also retrieve the logs for any execution:

   .. code-block:: bash

      $ curl localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533/executions/27326d48-7f00-4a45-a2f7-76fff8d685e6/logs

   Response:

   .. code-block:: JSON

        {
            "msg": "Logs retrieved successfully.",
            "result": "Contents of MSG: execute yourself\nEnvironment:\nHOSTNAME=f64b9adb8239\nSHLVL=1\nHOME=/root\n_abaco_api_server=https://dev.tenants.staging.agaveapi.co\nMSG=execute yourself\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\nPWD=/\n_abaco_username=anonymous\n",
            "status": "success",
            "version": "0.01"
        }

   As mentioned earlier, this test container simply  echo's the environment, and we see that from the logs. Notice that
   our ``MSG`` variable showed up, as well as a couple other variables: ``_abaco_api_server`` and ``_abaco_username``.
   The abaco system has a configurable authentication mechanism for securing the services with standards such as JWT
   (https://tools.ietf.org/html/rfc7519).



Additional Features
===================

The quick start introduced the basic features of abaco, but there's a lot more to explore.

- Admin API: In abaco, messages sent to an actor for execution are queued and processed by the actor's "workers". Workers
  are processes that have access to the docker daemon and the actor's image, and workers take care of launching the
  actor containers, reading the docker stats api for the execution, store logs for the execution, etc. abaco has a
  separate administration api which can be used to manage the workers for an actor. This
  API is available via the ``workers`` collection for any given actor: for example, to retrieve the workers for our
  actor from the quickstart we would make a GET request like so:

  .. code-block:: bash

    $ curl localhost:8000/actors/e68ebbb7-4986-46ee-9332-a1f5cfc6a533/workers

  The response will container a list of all workers including the container id, host ip and status.

  .. code-block:: JSON

        {
            "msg": "Workers retrieved successfully.",
            "result": {
                "656fdef81bef4a0aa564f4880c1e8380": {
                    "ch_name": "656fdef81bef4a0aa564f4880c1e8380",
                    "cid": "1e7625aa897f6409498d7a455b1a51482dceca0d16dc2521f34add16b4ba4f7f",
                    "host_id": "0",
                    "host_ip": "172.17.0.1",
                    "image": "jstubbs/abaco_test",
                    "last_execution": 0,
                    "location": "unix://var/run/docker.sock",
                    "status": "READY",
                    "tenant": "dev_staging"
                }
            },
            "status": "success",
            "version": "0.01"
        }

  We can add workers for an actor by making POST requests to the collection, optionally passing an argument
  ``num`` to specify a number of workers to have (default is 1). Note that when an actor has multiple workers, messages
  will be processed in parallel. We can also delete a worker by making a DELETE request to the worker's URI.

- Privileged containers: By default, all actor containers are started in non-privileges mode, but when registering an
  actor, the user can specify the actor is ``privileged`` in which case containers will be started in privileged mode
  with the docker daemon mounted. This can be used, for example, to kick off automated Docker builds of other images.

- Stateless actors: By default, actors are assumed to be statefull (that is, have side effects or maintain
  state between executions), but when registered, an actor can be set as "stateless" indicating that they can be
  automatically scaled (that is, add additional workers) without race conditions (see below).

- Health checks and auto-scaling: currently, abaco runs a health check process to ensure that workers are healthy and
  available for messages in an actor's queue. The health check agent can create new workers and/or destroy existing
  workers as needed, depending on an actor's queue size. We are currently working on formalized policies that can be
  set in the ``abaco.conf`` file to allow for more robust auto-scaling, including that of stateless actors.

- Hot updates and graceful shutdowns: workers can be sent a "shutdown" command which will cause the worker to exit. If
  the worker is currently processing an actor execution, the execution will conclude before the worker exits. When
  updating an actor's image, abaco first gracefully shuts down all workers before launching new workers with the updated
  image so that actors are in effect updated in real time with no downtime or execution interruption.

- Scalable architecture and Multihost deployments: Abaco was architected to scale easily to meet the demands of
  large workloads across thousands of actors. While the quickstart launched all abaco processes (or actors!) on a single
  host, but the system can be deployed and scaled up across any number of hosts. See the ``ansible``
  directory for scripts used to deploy abaco in production-like environments. For more information on the abaco
  architecture see (https://github.com/TACC/abaco/blob/master/docs/architecture.rst).
  UPDATE: with the announcement of
  Docker 1.12 and embedded orchestration, parts of this section will be updated to make deploying on a swarm
  cluster seamless and automatic from the compose file.

- Configurable: Many aspects of the abaco system are configured in the abaco.conf file. The example contained in this
  repository is self-documenting.

- Multi-tenant: A single deployment can serve multiple organization or "tenants" which have logical separation within
  the abaco system. The tenants can be configured in the ``abaco.conf`` file and read out of the request through either
  a JWT or a special tenant header.

- Integration with the Agave (http://agaveapi.co/) science-as-a-service API platform: abaco can be used as an "event
  processor" in conjunction with the Agave API platform. When deployed and configured with Agave's JWT authentication,
  abaco will inject the necessary authentication tokens needed for making requests directly to Agave APIs on behalf of the
  original end-user. Additionally, we are developing base images that contain Agave language SDKs and other tools so that
  processing an event can be as easy as writing a function or extending a class.




