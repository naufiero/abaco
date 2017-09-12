## abaco_test ##

This is a small image built off busybox that can be used for basic testing of the Abaco runtime.
The image runs a small shell script to: echo the MSG variable, echo the entire enviroment, and list the root
file system. It also runs a short sleep which means that sufficient load on the messages endpoint will
result in queueing of messages. This can be used to test scaling features.