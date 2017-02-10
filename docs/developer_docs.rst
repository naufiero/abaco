===============================
abaco - Developer Documentation
===============================

This section goes into more technical details about the configuration and implementation of Abaco.


Configurations
==============
The Abaco system has several configuration options. Configurations are placed in the abaco.conf file and
mounted into the initial containers for the web applications, spawners, health supervisors, and client generators.
For containers started dynamically, such as the worker containers, the conf file must be present on the host
and the path to the file must be known by the agents starting the containers (such as the spawners in the case of
workers). Abaco agents look for the environment variable "abaco_conf_host_path" to know where to mount the conf
file from on the host. In the local development docker-compose file, we set the abaco_conf_host_path based on the
variable "abaco_path", which should be a directory containing a config file (for example, the github project
root). For example, to get started locally, once can put `export abaco_path=$(pwd)` from within the project
root and the compose file will use the local-dev.conf file there (see the Abaco README.rst in the project root).

The abaco.conf file in the project root should be self documenting and contain all possible options. Here we want
to highlight some of the bigger, more important config options

1) The database used: Current options are Mongo 3 and Redis. The store.py module provides the interface and
implementation for each so that another database could be added relatively easily. Redis provides better
performance and more complete transaction semantics but the entire dataset must live in memory or else
we will have to implement sharding in our application. Mongo3 spools to disk meaning it doesn't have the spacial
shortcomings, however, as of 3.4, it does not provide complete transaction semantics. See "Database Considerations"
below.

2) Whether to generate clients: The Abaco system can be configured to dynamically generate an OAuth client as well as
a set of access tokens whenever it starts a worker. In this situation, the worker will maintain a valid access token
(using a refresh token, as needed) representing the owner of the actor, and inject that access token into the actor
container. (Note that the actor currently has no way of refreshing the token herself, so such executions should be
restricted to the life of the token, typically 4 hours). It is possible to turn off client generation by setting
`generate_clients: False` within the workers stanza of the config file. See "Client Generation" below.



Development
===========

Actors and Communication via Channels
=====================================

Abaco itself is largely architected using an Actor model. Actors communicate to each other by passing messages over
a "channel". Channels are first class objects that enable communication across Python threads processes or hosts, and
the Channel objects themselves can be passed through the channels. This approach enables both pub-sub as well as
direct request-reply patterns. We use the channelpy library (https://github.com/TACC/channelpy) as the basis for our
channels.

The channels in use in the system are defined in the channels.py module (within the actors package).


Database Considerations
=======================

We divide up the state persisted in the Abaco system into "stores" defined in the stores.py module. Each of
these stores represent an independent collection of data (though there are relations) and, in theory, could be
stored in different databases.

One potential option is to use a mix of databases. For example. we could use Redis for current application state
(e.g. actors_store and workers_store) where transaction semantics could be more useful and the size of the
dataset will be relatively small, and use Mongo for the accounting and logging data (executions_store and
logs_store). Naturally, the log data (actual raw logs from the container executions) presents a challenge in
space, and was one of the primary reasons for adding support for Mongo. We already use a set_with_expiry method
to store the logs for a fixed period of time.


Client Generation
=================

The Abaco system uses a separate backend process (or "actor") for generating clients. Other actors in the system, such
as the Spawners, communication


Dependence on Docker version
=============================


Running the Tests
=================


Staging and Production
======================

