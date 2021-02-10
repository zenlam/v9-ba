#!/bin/bash

#variable from python
dest_ip=$1
dest_port=$2
dest_login=$3
dest_pass=$4

# Generate a public key if it doesn't exist
echo -e "\n" | ssh-keygen -t rsa -N ""

# Copy the public key to the destination server to establish a public key authentication
sshpass -p $dest_pass ssh-copy-id -o StrictHostKeyChecking=no -p $dest_port $dest_login@$dest_ip