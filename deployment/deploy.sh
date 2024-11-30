#!/bin/bash

# Setup
apt install docker.io unzip -y

# Cleaning previous agent
rm -rf /root/libertai-agent
docker stop libertai-agent && docker rm $_

# Deploying the new agent
unzip /tmp/libertai-agent.zip -d /root/libertai-agent
wget https://raw.githubusercontent.com/Libertai/libertai-agents/refs/heads/reza/deployment-instances/deployment/$2.Dockerfile -O /tmp/libertai-agent.Dockerfile -q
docker build /root/libertai-agent \
  -f /tmp/libertai-agent.Dockerfile \
  -t libertai-agent \
  --build-arg PYTHON_VERSION=$1
docker run --name libertai-agent -p 8000:8000 -d libertai-agent
