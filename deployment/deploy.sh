#!/bin/bash

ZIP_PATH="/tmp/libertai-agent.zip"
CODE_PATH="/root/libertai-agent"
DOCKERFILE_PATH="/tmp/libertai-agent.Dockerfile"

case "$3" in
    fastapi)
        ENTRYPOINT="fastapi run src/main.py"
        ;;
    python)
        ENTRYPOINT="python -m src.main"
        ;;
esac

# Setup
apt update
apt install docker.io unzip -y

# Cleaning previous agent
rm -rf $CODE_PATH
docker stop libertai-agent && docker rm $_

# Deploying the new agent
unzip $ZIP_PATH -d $CODE_PATH
wget https://raw.githubusercontent.com/Libertai/libertai-agents/refs/heads/reza/instances/deployment/$2.Dockerfile -O $DOCKERFILE_PATH -q --no-cache
docker build $CODE_PATH \
  -f $DOCKERFILE_PATH \
  -t libertai-agent \
  --build-arg PYTHON_VERSION=$1
docker run --name libertai-agent -p 8000:8000 -d libertai-agent $ENTRYPOINT

# Cleanup
rm -f $ZIP_PATH
# rm -rf $CODE_PATH
rm -f $DOCKERFILE_PATH
