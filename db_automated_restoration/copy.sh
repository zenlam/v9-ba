#!/bin/bash

set -e

timestamp(){
   echo -n `date --date="8 hours" "+%Y-%m-%d %H:%M:%S,"`
}

#variable from python
dest_ip=$1
dest_port=$2
dest_login=$3
source_path=$4
dest_path=$5
db_user=$6
db_name=$7
dest_full_path=$8
remove_old=$9
restore_script=${10}
remove_dump=${11}
sql_query=${12}
redo=${13}
su_password=${14}


# Copy the dump file from the server to Destination Server with Rsync method
timestamp; echo " Start to copy $dest_full_path to $dest_ip."
timeout 1800 rsync -chavzP -e "ssh -p $dest_port" $source_path $dest_login@$dest_ip:$dest_path
timestamp; echo " The file is copied."


# ssh to Destination Server and run the script
timestamp; echo " SSH into $dest_ip:$dest_port as $dest_login."
ssh -p $dest_port -l $dest_login $dest_ip "bash -s" < $restore_script $db_user $db_name $dest_full_path $remove_old $remove_dump "\"$sql_query\"" $redo "\"$su_password\""
timestamp; echo " Exit $dest_ip."
timestamp; echo " The job is executed successfully."
