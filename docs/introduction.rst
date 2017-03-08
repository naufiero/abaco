============
Introduction
============

Abaco (Actor based containers/computing) is a platform for deploying, executing and scaling distributed systems based on
the actor model of concurrent computation. In abaco, the computational primitives (referred to as "actors") are each
defined by a Docker container image and communicate via messages passed over http. This approach makes it easy to run
distributed computing systems composed of components build in completely different technologies. Additionally, systems
build in this way enjoy the benefits of an actor system: a concurrency model that is easy to understand and reason
about. Since each actor's inbox corresponds to a URI, actors registered in abaco can be used to process web-callbacks
and other "events".