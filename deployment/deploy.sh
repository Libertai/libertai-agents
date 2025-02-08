#!/bin/bash

ZIP_PATH="/tmp/libertai-agent.zip"
CODE_PATH="/root/libertai-agent"
DOCKERFILE_PATH="/tmp/libertai-agent.Dockerfile"
CONTAINER_NAME="libertai-agent"

case "$3" in
    fastapi)
        ENTRYPOINT="fastapi run src/main.py"
        ;;
    python)
        ENTRYPOINT="python -m src.main"
        ;;
esac

# Setup
export DEBIAN_FRONTEND=noninteractive # Suppress debconf warnings
apt-get update
apt-get install unzip -y
if ! command -v docker &> /dev/null; then
    # Docker installation when not already present
    curl -fsSL https://get.docker.com | sudo DEBIAN_FRONTEND=noninteractive sh 2>/dev/null
    sudo usermod -aG docker $USER  # Allow non-root usage
    sudo systemctl enable --now docker 2>/dev/null # Start Docker and enable on boot
fi


# Cleaning previous agent
rm -rf $CODE_PATH
docker inspect libertai-agent 2>/dev/null && docker stop libertai-agent && docker rm libertai-agent

# Deploying the new agent
unzip $ZIP_PATH -d $CODE_PATH
wget https://raw.githubusercontent.com/Libertai/libertai-agents/refs/heads/main/deployment/$2.Dockerfile -O $DOCKERFILE_PATH -q --no-cache
docker buildx build -q $CODE_PATH \
  -f $DOCKERFILE_PATH \
  -t libertai-agent \
  --build-arg PYTHON_VERSION=$1
docker run --name $CONTAINER_NAME -p 8000:8000 -d libertai-agent $ENTRYPOINT

# Cleanup
rm -f $ZIP_PATH
rm -rf $CODE_PATH
rm -f $DOCKERFILE_PATH
