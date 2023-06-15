#!/usr/bin/env python3
import json
import boto3

def get_instance_details(region):
    ec2 = boto3.resource('ec2', region_name=region)

    instances = ec2.instances.all()

    instance_list = []

    for instance in instances:
        instance_dict = {}
        instance_dict['FQDN'] = instance.public_dns_name
        instance_dict['Hostname'] = instance.private_dns_name
        instance_dict['Internal IP'] = instance.private_ip_address
        instance_dict['External IP'] = instance.public_ip_address
        instance_dict['VPC'] = instance.vpc.id
        instance_dict['State'] = instance.state['Name']
        instance_dict['Subnet ID'] = instance.subnet_id
        # Retrieve Network Security Group details
        security_groups = []
        for group in instance.security_groups:
            security_groups.append({
                'GroupName': group['GroupName'],
                'GroupId': group['GroupId']
            })
        instance_dict['Security Groups'] = security_groups

        # Retrieve tags
        tags = {tag['Key']: tag['Value'] for tag in instance.tags or []}
        instance_dict['Tags'] = tags

        instance_list.append(instance_dict)

    return instance_list

def get_all_instance_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_instance_details = {}

    for region in regions:
        region_name = region['RegionName']
        instances = get_instance_details(region_name)
        all_instance_details[region_name] = instances

    return all_instance_details

all_instance_details = get_all_instance_details()
print(json.dumps(all_instance_details))
