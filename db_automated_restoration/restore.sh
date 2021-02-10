#!/bin/bash

set -e

timestamp(){
   echo -n `date "+%Y-%m-%d %H:%M:%S,"`
}

#variable from previous script
db_user=$1
db_name=$2
dest_full_path=$3
remove_old=$4
remove_dump=$5
sql_query=$6
redo=$7
su_password=$8

# drop the previous failed database if redo
if $redo;
then
    timestamp; echo " Dropping the existing database named $db_name with owner $db_user."
    # terminate the database backend activity
    echo "$su_password" | sudo -S -u postgres psql -c "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db_name' AND pid <> pg_backend_pid();"
    timestamp; echo " Terminated the backend activity of the existing database $db."
    # drop the database
    echo "$su_password" | sudo -S -u postgres psql -c "DROP DATABASE \"$db_name\""
    timestamp; echo " Old database is dropped: $db_name."
fi

# create a new database
timestamp; echo " Creating a new database named $db_name with owner $db_user."
echo "$su_password" | sudo -S -u postgres createdb -O $db_user $db_name

# restore the database using the dump file
timestamp; echo " Restoring the $db_name."
timeout 7200 echo "$su_password" | sudo -S -u postgres pg_restore --no-acl -O --role=$db_user -v -d $db_name < $dest_full_path || true
timestamp; echo " $db_name is restored."

# run the query if the user has any
if [ "$sql_query" != 'no_query' ]
then
    echo "$su_password" | sudo -S -u postgres psql -d $db_name -c "$sql_query"
fi
timestamp; echo " Query is executed."

# if remove_old is checked, retrieve the old database name and drop them
if $remove_old;
then
    # get the old databases name which is from the same owner and has a different name
    old_dbs=`sudo -u postgres psql -c "SELECT '\"'||d.datname||'\"' FROM pg_catalog.pg_database d WHERE pg_catalog.pg_get_userbyid(d.datdba) = '$db_user' and d.datname != "\'$db_name\'";"`
    timestamp; echo " Start to drop old database(s)."

    for db in $old_dbs
    do
    if [[ $db == \"* ]];
    then
        db_wo_quote="$(echo -e "${db}" | tr -d \" )"
        # terminate the database backend activity
        echo "$su_password" | sudo -S -u postgres psql -c "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$db_wo_quote' AND pid <> pg_backend_pid();"
        timestamp; echo " Terminated the backend activity of database $db."
        # drop the database
        echo "$su_password" | sudo -S -u postgres psql -c "DROP DATABASE $db"
        timestamp; echo " Old database is dropped: $db."
    fi
    unset old_dbs
    done
fi

# if remove_dump is checked, delete the dump file after the database restoration
if $remove_dump;
then
#remove the dump file
    timestamp; echo " Removed the dump file: $dest_full_path."
	echo "$su_password" | sudo -S rm $dest_full_path
fi