#!/usr/bin/env python3
import json
import boto3

def get_route_tables_by_subnet(region):
    ec2 = boto3.client('ec2', region_name=region)
    subnets = ec2.describe_subnets()
    
    subnet_data = []

    for subnet in subnets['Subnets']:
        subnet_id = subnet['SubnetId']
        route_tables = []
        
        # Describe route tables associated with the subnet
        associated_route_tables = ec2.describe_route_tables(Filters=[{'Name': 'association.subnet-id', 'Values': [subnet_id]}])
        
        for route_table in associated_route_tables['RouteTables']:
            route_table_info = {
                'RouteTableId': route_table['RouteTableId'],
                'Routes': route_table['Routes'],
                'Tags': {tag['Key']: tag['Value'] for tag in route_table.get('Tags', [])}
            }
            route_tables.append(route_table_info)
        
        subnet_data.append({
            'SubnetId': subnet_id,
            'RouteTables': route_tables
        })

    return subnet_data

def get_all_route_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_route_details = {}

    for region in regions:
        region_name = region['RegionName']
        route_details = get_route_tables_by_subnet(region_name)
        all_route_details[region_name] = route_details

    return all_route_details


if __name__ == "__main__":
    route_dets = get_all_route_details()


    with open('route_subnet_data.json', 'w') as outfile:
        json.dump(route_dets, outfile)