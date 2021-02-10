# -*- coding: utf-8 -*-

{
    'name': 'Database Automated Restoration',
    'version': '1.1',
    'summary': 'Automated Database Restoration from Server to Server',
    'author': "ONNET SOLUTIONS SDN BHD",
    'sequence': 30,
    'description': """A module that allows the user to perform database restoration to a remote server using a dump file.
                     The dump file will be copied from the local to the remote server and the credentials of remote server
                     will be needed to establish public key connection to perform automated database restoration. In order
                     to use this module, it is required to install rsync and sshpass. The command to install rysnc and sshpass 
                     can be found in ubuntu_requirement.sh and centos_requirement.sh for the respective OS. Currently, this 
                     module is working on Ubuntu and CentOS.""",
    'website': 'http://www.on.net.my',
    'depends': [
        'base'
    ],
    'data': [
        'views/db_automated_restoration.xml',
        'security/ir.model.access.csv'
    ],
    'installable': True,
    'application': True,
}
