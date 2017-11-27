#!/bin/bash
#
# Docker entrypoint for the test suite. This script needs the docker daemon mounted. It will
# To run specific tests, pass the same argument as would be passed to py.test.
#

# Parameter to the entrypoint.
TEST=$1



# if nothing passed, run the full suite
if [ -z $TEST ]; then
  py.test /tests/test_abaco_core.py
else
  py.test $TEST
fi