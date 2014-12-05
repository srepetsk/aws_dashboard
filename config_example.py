#!/usr/bin/python
# vim: set expandtab:
import os
def get_ec2_conf():
    AWS_ACCESS_KEY_ID = 'YOUR ACCESS KEY ID'
    AWS_SECRET_ACCESS_KEY = 'YOUR SECRET ACCESS KEY'
    return {'AWS_ACCESS_KEY_ID' : AWS_ACCESS_KEY_ID, 'AWS_SECRET_ACCESS_KEY' : AWS_SECRET_ACCESS_KEY}

def region_list():
    region_list = ['us-east-1','us-west-1','us-west-2']
    return region_list

def filter_instance_shutdown():
        SHUTDOWN_TAG_TYPE = '"USE" TAG VALUE TO FILTER ON'
        return {'SHUTDOWN_TAG_TYPE' : SHUTDOWN_TAG_TYPE }

def get_secret_key():
        SECRET_KEY = 'YOUR RANDOMLY-GENERATED SECRET KEY'
        return {'SECRET_KEY' : SECRET_KEY}
