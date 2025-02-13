#!/bin/bash

SSH_PUBLIC_KEY=$1

# Add key only if's not already in the file
if grep -qxF "$SSH_PUBLIC_KEY" ~/.ssh/authorized_keys; then
    echo "Error: Given SSH key already in ~/.ssh/authorized_keys" >&2
    exit 1
fi

echo "$SSH_PUBLIC_KEY" >> ~/.ssh/authorized_keys
