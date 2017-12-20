#!/bin/bash

# print the special MSG variable:
echo "Contents of MSG: "$MSG

# do a sleep to slow things down
sleep 2

# print the full environment
echo "Environment:"
env

# print the root file system:
echo "Contents of root file system: "
ls /

# check for the default mounts
echo "Checking for contents of mounts:"
if [ -e /_abaco_data1 ]; then
  echo "Mount exsits. Contents:"; ls /_abaco_data1
else
  echo "Mount does not exist"
fi;

# check for work and corral
echo "****Contents of jstubbs work:****"
ls -l /work/01837/jstubbs

echo "****Contents of /corral:****"
ls -l /corral