#!/usr/bin/env python3
import json
import boto3

class SecurityGroup:
    def __init__(self, session):
        self.session = session

    def get_security_group_details(self, region):
        ec2 = self.session.client('ec2', region_name=region)

        response = ec2.describe_security_groups()
        
        security_group_list = []

        for security_group in response['SecurityGroups']:
            security_group_dict = {}
            security_group_dict['GroupName'] = security_group['GroupName']
            security_group_dict['GroupId'] = security_group['GroupId']
            security_group_dict['Description'] = security_group['Description']

            inbound_permissions = []
            for permission in security_group['IpPermissions']:
                inbound_permissions.append({
                    'IpProtocol': permission.get('IpProtocol'),
                    'FromPort': permission.get('FromPort'),
                    'ToPort': permission.get('ToPort'),
                    'UserIdGroupPairs': permission.get('UserIdGroupPairs', []),
                    'IpRanges': permission.get('IpRanges', []),
                    'Ipv6Ranges': permission.get('Ipv6Ranges', []),
                    'PrefixListIds': permission.get('PrefixListIds', [])
                })
            security_group_dict['InboundRules'] = inbound_permissions

            outbound_permissions = []
            for permission in security_group['IpPermissionsEgress']:
                outbound_permissions.append({
                    'IpProtocol': permission.get('IpProtocol'),
                    'FromPort': permission.get('FromPort'),
                    'ToPort': permission.get('ToPort'),
                    'UserIdGroupPairs': permission.get('UserIdGroupPairs', []),
                    'IpRanges': permission.get('IpRanges', []),
                    'Ipv6Ranges': permission.get('Ipv6Ranges', []),
                    'PrefixListIds': permission.get('PrefixListIds', [])
                })
            security_group_dict['OutboundRules'] = outbound_permissions

            security_group_list.append(security_group_dict)

        return security_group_list

    def get_all_security_group_details(self):
        ec2_client = self.session.client('ec2')
        regions = ec2_client.describe_regions()['Regions']

        all_security_group_details = {}

        for region in regions:
            region_name = region['RegionName']
            security_groups = self.get_security_group_details(region_name)
            all_security_group_details[region_name] = security_groups

        return all_security_group_details

    def main(self):
        all_security_group_details = self.get_all_security_group_details()

        # Save the details to a file named 'security_group_data.json'
        with open('security_group_data.json', 'w') as outfile:
            json.dump(all_security_group_details, outfile)

