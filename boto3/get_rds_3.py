#!/usr/bin/env python3
import json
import boto3

def get_rds_details(region):
    rds = boto3.client('rds', region_name=region)

    db_instances = rds.describe_db_instances()

    db_details_list = []

    for db in db_instances['DBInstances']:
        db_details = {}
        db_details['DBInstanceIdentifier'] = db['DBInstanceIdentifier']
        db_details['DBInstanceStatus'] = db['DBInstanceStatus']
        db_details['Engine'] = db['Engine']
        db_details['EngineVersion'] = db['EngineVersion']
        db_details['DBInstanceClass'] = db['DBInstanceClass']
        db_details['MasterUsername'] = db['MasterUsername']
        db_details['VPCId'] = db['DBSubnetGroup']['VpcId']
        db_details['MultiAZ'] = db['MultiAZ']
        db_details['PubliclyAccessible'] = db['PubliclyAccessible']
        db_details['StorageEncrypted'] = db['StorageEncrypted']
        db_details['IAMDatabaseAuthenticationEnabled'] = db['IAMDatabaseAuthenticationEnabled']
        db_details['Endpoint'] = db['Endpoint']['Address']
        db_details['Port'] = db['Endpoint']['Port']
        db_details['BackupRetentionPeriod'] = db['BackupRetentionPeriod']

        # Check if DBName key exists
        if 'DBName' in db:
            db_details['DBName'] = db['DBName']

        # Retrieve Security Groups
        security_groups = []
        for group in db['VpcSecurityGroups']:
            security_groups.append({
                'VpcSecurityGroupId': group['VpcSecurityGroupId'],
                'Status': group['Status']
            })
        db_details['VpcSecurityGroups'] = security_groups

        db_details_list.append(db_details)

    return db_details_list

def get_all_rds_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_rds_details = {}

    for region in regions:
        region_name = region['RegionName']
        dbs = get_rds_details(region_name)
        all_rds_details[region_name] = dbs

    return all_rds_details

all_rds_details = get_all_rds_details()
print(json.dumps(all_rds_details))
