#!/usr/bin/env python3
import json
import boto3

def get_vpc_peering_details(region):
    ec2 = boto3.client('ec2', region_name=region)

    peering_connections = ec2.describe_vpc_peering_connections()

    peering_details_list = []

    for peering in peering_connections['VpcPeeringConnections']:
        peering_details = {}
        peering_details['PeeringConnectionId'] = peering['VpcPeeringConnectionId']
        peering_details['Status'] = peering['Status']['Code']
        peering_details['RequesterVPC'] = peering['RequesterVpcInfo']['VpcId']
        peering_details['AccepterVPC'] = peering['AccepterVpcInfo']['VpcId']
        
        # Check if Tags key exists
        if 'Tags' in peering:
            tags = {tag['Key']: tag['Value'] for tag in peering['Tags']}
            peering_details['Tags'] = tags

        peering_details_list.append(peering_details)

    return peering_details_list

def get_all_vpc_peering_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_peering_details = {}

    for region in regions:
        region_name = region['RegionName']
        peering_details = get_vpc_peering_details(region_name)
        all_peering_details[region_name] = peering_details

    return all_peering_details

#all_peering_details = get_all_vpc_peering_details()
#print(json.dumps(all_peering_details))
if __name__ == "__main__":
    all_peering_details = get_all_vpc_peering_details()

    # Save the details to a file named 'alb_data'
    with open('vpc_peering_data.json', 'w') as outfile:
        json.dump(all_peering_details, outfile)