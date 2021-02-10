#!/bin/bash

dest_ip=$1
dest_port=$2
dest_login=$3

# check if the public key authentication exists
ssh -o BatchMode=yes -p $dest_port -l $dest_login $dest_ip exit

