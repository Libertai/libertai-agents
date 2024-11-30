#!/bin/bash

# Setup
apt install docker.io -y

# Cleaning previous agent
rm -rf /root/libertai-agent
docker stop libertai-agent && docker rm $_

# Deploying the new agent
unzip /tmp/libertai-agent.zip -d /root/libertai-agent
wget https://TODO -o /tmp/libertai-agent.Dockerfile
docker build /root/libertai-agent \
  -f /tmp/libertai-agent.Dockerfile \
  -t libertai-agent \
  --build-arg PYTHON_VERSION=$1
docker run -p 8000:8000 libertai-agent
