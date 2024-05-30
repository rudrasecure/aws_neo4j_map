#!/usr/bin/env python3
import json
import boto3

def get_security_group_details(region):
    ec2 = boto3.client('ec2', region_name=region)

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

def get_all_security_group_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_security_group_details = {}

    for region in regions:
        region_name = region['RegionName']
        security_groups = get_security_group_details(region_name)
        all_security_group_details[region_name] = security_groups

    return all_security_group_details

#all_security_group_details = get_all_security_group_details()
#print(json.dumps(all_security_group_details))
if __name__ == "__main__":
    all_security_group_details = get_all_security_group_details()

    # Save the details to a file named 'alb_data'
    with open('security_group_data.json', 'w') as outfile:
        json.dump(all_security_group_details, outfile)