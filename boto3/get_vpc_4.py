#!/usr/bin/env python3
import json
import boto3

def get_vpc_peering_details(region):
    ec2 = boto3.client('ec2', region_name=region)

    peering_connections = ec2.describe_vpc_peering_connections()

    peering_details_map = {}

    for peering in peering_connections['VpcPeeringConnections']:
        peering_details = {
            'PeeringConnectionId': peering['VpcPeeringConnectionId'],
            'Status': peering['Status']['Code'],
            'RequesterCidr': peering['RequesterVpcInfo']['CidrBlock'],
            'AccepterCidr': peering['AccepterVpcInfo']['CidrBlock']
        }
    
        # Check if Tags key exists
        if 'Tags' in peering:
            tags = {tag['Key']: tag['Value'] for tag in peering['Tags']}
            peering_details['Tags'] = tags

        peering_details_map.setdefault(peering['RequesterVpcInfo']['VpcId'], []).append(peering_details)
        peering_details_map.setdefault(peering['AccepterVpcInfo']['VpcId'], []).append(peering_details)
    
    return peering_details_map

def get_all_vpcs_with_peering(region):
    ec2 = boto3.client('ec2', region_name=region)
    vpc_details = ec2.describe_vpcs()
    
    peering_details = get_vpc_peering_details(region)
    
    all_vpc_data = []

    for vpc in vpc_details['Vpcs']:
        vpc_id = vpc['VpcId']
        vpc_info = {
            'VpcId': vpc_id,
            'CidrBlock': vpc['CidrBlock'],
            'IsDefault': vpc['IsDefault'],
            'PeeringConnections': peering_details.get(vpc_id, []) 
        }
        if 'Tags' in vpc:
            vpc_info['Tags'] = {tag['Key']: tag['Value'] for tag in vpc['Tags']}

        all_vpc_data.append(vpc_info)

    return all_vpc_data

def get_all_vpc_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_vpc_details = {}

    for region in regions:
        region_name = region['RegionName']
        vpc_details = get_all_vpcs_with_peering(region_name)
        all_vpc_details[region_name] = vpc_details

    return all_vpc_details

#all_peering_details = get_all_vpc_peering_details()
#print(json.dumps(all_peering_details))
if __name__ == "__main__":
    all_peering_details = get_all_vpc_details()

    # Save the details to a file named 'alb_data'
    with open('vpc_peering_data.json', 'w') as outfile:
        json.dump(all_peering_details, outfile)