
Abaco - Architecture Overview
-----------------------------

Abaco is a distributed system made up of independent components that run as isolated processes. The components can
be broken down into synchronous, frontend APIs and asynchronous, backend processes:

**Frontend**
* registration API
* messages API
* admin API

**Backend**

* spawners
* workers
* health checks

In addition to the above components, Abaco makes use of Redis, MongoDB and RabbitMQ for persistence. Communication between the
processes is achieved through message passing via RabbitMQ. Abaco makes heavy use of channels (inspired from Go channels, see
https://github.com/TACC/channelpy) to facilitate both direct communication as well as pub/sub. Four types of channels are used - the command channel, worker channels, actor message channels and anonymous channels. See the channels.py module for more details.


Frontend Components
-------------------

Each frontend component is a flask-restful web application running behind nginx. The frontend components all accept and return JSON. They have been broken out into three separate applications for independent scalability. Their duties are as follows:

- registration API - register and maintain actors; list, create, update and delete details of an actor. Persist details into the Mongo and Redis databases. List executions for an actor. List logs for an exectution. Creates messages on the command channel to instruct spawners to create new workers when actors are registered.

- messages API - POST messages to an actor's inbox, scheduling the execution of a container from the actor's image. Will also return pending messages from the actor's queue. Creates messages on actor message channels to instruct workers to execute containers for their actor.

- admin API - list, create and delete workers for an actor. Creates messages on worker channels to instruct workers to shutdown, and creates messages on the command channel to create new workers.


Backend Components
------------------
Each backend component runs as a Python process running inside its own Docker container.

- spawners - these processes listen to the the command channel and spawn new workers when an actor is registered or updated.

- workers - these processes listen to a specific actor message channel and execute containers when a new message arrives.

- health checks - these processes run on a schedule (e.g., via cron) to check the status of workers and to ensure the number of workers for a given actor meets some requirements.

- clientg - these processes listen to the clients channel for new client and client deletion requests. They leverage a Python 3-compatible Agave SDK to manage clients for the workers.