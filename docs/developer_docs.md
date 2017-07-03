
Abaco - Developer Documentation
-------------------------------

This section goes into more technical details about the configuration and implementation of Abaco.


Configurations
--------------
The Abaco system has several configuration options. Configurations are placed in the abaco.conf file and
mounted into the initial containers for the web applications, spawners, health supervisors, and client generators.
For containers started dynamically, such as the worker containers, the conf file must be present on the host
and the path to the file must be known by the agents starting the containers (such as the spawners in the case of
workers). Abaco agents look for the environment variable "abaco_conf_host_path" to know where to mount the conf
file from on the host. In the local development docker-compose file, we set the abaco_conf_host_path based on the
variable "abaco_path", which should be a directory containing a config file (for example, the github project
root). For example, to get started locally, once can put `export abaco_path=$(pwd)` from within the project
root and the compose file will use the local-dev.conf file there (see the Abaco README.md in the project root).

The abaco.conf file in the project root should be self documenting and contain all possible options. Here we want
to highlight some of the bigger, more important config options

1) Logging: Abaco has two kinds of logging configuration. First is the log strategy to use, which can be either 'combined' so that all logs go into one file or 'split' so that each process logs to a separate file. Second, logging can be configured by level ('CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'). Log level can be set for the entire Abaco instance all at once (e.g. level = WARN) or for specific modules (e.g level.spawner = DEBUG).

2) Whether to generate clients: The Abaco system can be configured to dynamically generate an OAuth client as well as
a set of access tokens whenever it starts a worker. In this situation, the worker will maintain a valid access token
(using a refresh token, as needed) representing the owner of the actor, and inject that access token into the actor
container. (Note that the actor currently has no way of refreshing the token herself, so such executions should be
restricted to the life of the token, typically 4 hours). It is possible to turn off client generation by setting
`generate_clients: False` within the workers stanza of the config file. See "Client Generation" below.



Development
-----------

To develop the core Abaco services, find or create an issue on github to work in. Checkout the project from github and
create a local feature branch from the development branch with name I-xyz where xyz is the number
of the issue on github.

All core modules live in the actors package. The modules ending in _api.py define Flask applications
 and associated resources. The resource implementations are all defined in the controllers.py module. The models.py
 module defines data access classes and methods for interacting with the persistence layer.

The store.py module defines high-level interfaces for interacting with databases, and stores.py provides specific
definitions of Abaco stores used in the models.py module.

The backend processes (e.g. spawners, workers, health checks and clientg) are defined in their own modules with a
 corresponding main method used for start up.

Channels used for communication between Abaco processes are implemented in the channels.py module.

Once code changes are in place, build a new abaco_core image (all core Abaco processes run out of the same
core image), relaunch the Abaco container stack, and run the tests. Add new tests as appropriate.

Building the Images, Launching the Stack, and Running the Tests (Linux)
-----------------------------------------------------------------------
Note: These instructions work for Linux. OS X and Windows will require different approaches.

**Building the Images**

All core Abaco processes run out of the same abaco/core image. It should be build using the Dockerfile at the root
of the repository and tagged with a tag equal to the branch name. Export a variable called $TAG with the tag name
preceded by a colon (:) character in it.

For example,

```shell
$ export TAG=:I-12
$ docker build -t abaco/core$TAG .
```
Auxiliary images can be built from the Dockerfiles within the images folder. In particular, the abaco/nginx image required
to start up the stack can built from within the images/nginx directory. For example

```shell
$ cd images/nginx
$ docker build -t abaco/nginx$TAG .
```

**Starting the Development Stack**

Once the images are built, start the development stack by first changing into the project root and
exporting the abaco_path and TAG variables. You also need to create an abaco.log file in the root:

```shell
$ export abaco_path=$(pwd)
$ export TAG=:I-12
$ touch abaco.log
```
The abaco_path variable needs to contain the path to a directory with an abaco.conf file. It is used by Abaco containers to
know where to find the config file. Note that the abaco.conf contains the default IP address of the Docker0 gateway for
Mongo and Redis. If your Docker0 gateway IP is different, you will need to updte the abaco.conf file.

Finally, start the Abaco containers with the following command:

```shell
$ docker-compose -f dc-all.yml up -d
```
Note that this will command will still run the default (production) versions of the auxiliary images, such as nginx
and the databases.


**Running the Tests**
There are two kinds of tests in the Abaco test suite: unit tests and functional tests. Unit tests target a specific
module while functional tests target the entire stack. The tests leverage py.test framework and each test module starts
with "test_" followed by either the name of a module or a description of the functions being tested. For example,
test_store.py contains unit tests for the store.py module while test_abaco_core.py contains functional tests for
the Abaco core functionality.

The tests are packaged into their own Docker image for convenience. To run the tests, first build the tests image:

```shell
$ docker build -f Dockerfile-test -t abaco/testsuite$TAG .
```

To run the functional tests, execute the following:

```shell
$ docker run -e base_url=http://172.17.0.1:8000 -e case=camel -v $(pwd)/local-dev.conf:/etc/service.conf -it --rm abaco/testsuite$TAG
```

Run the unit tests with a command similar to the following, changing the test module as the end as necessary:

```shell
$ docker run -e base_url=http://172.17.0.1:8000 -v $(pwd)/local-dev.conf:/etc/service.conf --entrypoint=py.test -it --rm abaco/testsuite$TAG /tests/test_store.py
```

Dev, Staging and Master Branches and Environments
-------------------------------------------------
The dev, staging and master branches are long-lived branches in the Abaco repository corresponding to the three
permanent environments: Dev, Staging and Production, respectively. Feature branches should be merged into dev
once tests are passing. Pushing dev to origin will then trigger an automated CI pipeline job in Jenkins which
will run tests and automatically deploy to the Dev environment. Deployment is done via Ansible scripts contained
in the ansible directory.


Actors and Communication via Channels
-------------------------------------

Abaco itself is largely architected using an Actor model. Actors communicate to each other by passing messages over
a "channel". Channels are first class objects that enable communication across Python threads, processes, or hosts, and
the Channel objects themselves can be passed through the channels. This approach enables both pub-sub as well as
direct request-reply patterns. We use the channelpy library (https://github.com/TACC/channelpy) as the basis for our
channels.

The channels in use in the system are defined in the channels.py module (within the actors package).


Database Considerations
-----------------------

We divide up the state persisted in the Abaco system into "stores" defined in the stores.py module. Each of
these stores represent an independent collection of data (though there are relations) and thus can be
stored in different databases.

We currently use both Redis and MongoDB for different stores. We use Redis for current application state
(e.g. actors_store and workers_store) where transaction semantics are needed and the size of the
dataset will be relatively small. We use Mongo for the permissions, accounting and logging data (permissions_store,
executions_store and logs_store). Naturally, the log data (actual raw logs from the container executions) presents a
challenge in space, and was one of the primary reasons for adding support for Mongo. We already use a set_with_expiry
method to store the logs for a fixed period of time.


Client Generation
-----------------

The Abaco system uses a separate backend process (or "actor") for managing OAuth clients. Each worker gets a new
OAuth client when it is started, and its client is deleted whenever the worker is destroyed. This way, the actor
containers can be started with a fresh OAuth access token. Currently, the clients modules leverages the agave.py module,
a Python 3-compatible Agave SDK for managing clients.


Dependence on Docker Version
----------------------------

Various functions within Abaco are implemented by making calls to the docker daemon API using the docker-py client.
These calls are implemented in the docker_utils.py module. Different versions of the docker-py client library as
well as the Docker daemon itself present different APIs, and this can impact performance and correctness within
Abaco. As a result, strict attention to Docker and docker-py versions is necessary.
