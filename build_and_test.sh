# Use this script to build all images and run the test suite.
# Assumes docker is installed locally.

# First, remove all containers and launch the dbs
printf "\n\n****** Abaco build and test script *******\n\n"
printf "Removing all containers...\n"
docker rm -f `docker ps -aq` || true

printf "\n\nLaunching databases...\n"
docker-compose -f docker-compose-local-db.yml up -d

# Build the core image
printf "\n\nBuilding core image...\n\n"
docker build -t jstubbs/abaco_core .

# Build the testsuite image
printf "\n\nBuilding testsuite image...\n\n"
docker build -t jstubbs/abaco_testsuite -f Dockerfile-test .

# abaco_path variable is needed so that addition containers can find the config file.
export abaco_path=$(pwd)

# first, launch the stack for camel case
printf "\n\nCamel case tests..\n"
printf "Updating config file.\n"
sed -i.bak 's/case: snake/case: camel/g' local-dev.conf
printf "Config file updated, launching abaco stack..\n"
docker-compose -f docker-compose-local.yml up -d
printf "Stack launched. Sleeping while stack starts up..."
sleep 5
printf "\n\nStack should be ready. Starting test suite...\n"
docker run -e base_url=http://172.17.0.1:8000 -e case=camel -v $(pwd)/local-dev.conf:/etc/service.conf -it --rm jstubbs/abaco_testsuite

printf "\n\n********* Test suite complete, removing containers...\n"
docker rm -f `docker ps -aq`
printf "Containers removed."

# next, launch stack for snake case
printf "\n\nSnake case tests..\n"
printf "Updating config file.\n"
sed -i.bak 's/case: camel/case: snake/g' local-dev.conf
printf "Config file updated, removing all containers...\n"
docker rm -f `docker ps -aq` || true
printf "Containers removed, launching abaco stack..\n"
docker-compose -f docker-compose-local-db.yml up -d
sleep 5
docker-compose -f docker-compose-local.yml up -d
printf "Stack launched. Sleeping while stack starts up...\n"
sleep 15
printf "\n\nStack should be ready. Starting test suite...\n"
docker run -e base_url=http://172.17.0.1:8000 -e case=snake -v $(pwd)/local-dev.conf:/etc/abaco.conf -it --rm jstubbs/abaco_testsuite

printf "\n\n********* Test suite complete, removing containers...\n"
docker rm -f `docker ps -aq`
printf "Containers removed. Build and test completed.\n\n"
