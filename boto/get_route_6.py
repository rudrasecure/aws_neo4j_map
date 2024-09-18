#!/usr/bin/env python3
import json
import boto3

class Route:
    def __init__(self, session):
        self.session = session

    def get_route_tables_by_subnet(self, region):
        ec2 = self.session.client('ec2', region_name=region)
        subnets = ec2.describe_subnets()
        
        subnet_data = []

        for subnet in subnets['Subnets']:
            subnet_id = subnet['SubnetId']
            subnet_cidr = subnet['CidrBlock']
            route_tables = []
            
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
                'CidrBlock': subnet_cidr,
                'RouteTables': route_tables
            })

        return subnet_data

    def get_all_route_details(self):
        ec2_client = self.session.client('ec2')

        regions = ec2_client.describe_regions()['Regions']

        all_route_details = {}

        for region in regions:
            region_name = region['RegionName']
            route_details = self.get_route_tables_by_subnet(region_name)
            all_route_details[region_name] = route_details

        return all_route_details

    def main(self):
        route_dets = self.get_all_route_details()

        # Save the details to a file named 'route_subnet_data.json'
        with open('route_subnet_data.json', 'w') as outfile:
            json.dump(route_dets, outfile)

