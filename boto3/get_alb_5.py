#!/usr/bin/env python3
import json
import boto3

def get_alb_details(region):
    client = boto3.client('elbv2', region_name=region)

    # Use pagination to handle possible large result set
    paginator = client.get_paginator('describe_load_balancers')
    page_iterator = paginator.paginate()

    alb_list = []
    for page in page_iterator:
        for alb in page['LoadBalancers']:
            if alb['Type'] in ['gateway']:
                continue
            alb_dict = {}
            alb_dict['LoadBalancerArn'] = alb['LoadBalancerArn']
            alb_dict['DNSName'] = alb['DNSName']
            alb_dict['VpcId'] = alb['VpcId']
            alb_dict['State'] = alb['State']
            alb_dict['Scheme'] = alb['Scheme']
            alb_dict['CreatedTime'] = alb['CreatedTime'].isoformat()
            alb_dict['SecurityGroups'] = alb['SecurityGroups']

            target_groups = client.describe_target_groups(
                LoadBalancerArn=alb['LoadBalancerArn'])

            alb_dict['TargetGroups'] = []
            for tg in target_groups['TargetGroups']:
                tg_dict = {}
                tg_dict['TargetGroupName'] = tg['TargetGroupName']
                tg_dict['TargetGroupArn'] = tg['TargetGroupArn']

                health_desc = client.describe_target_health(
                    TargetGroupArn=tg['TargetGroupArn'])

                tg_dict['Targets'] = []
                for th in health_desc['TargetHealthDescriptions']:
                    target_dict = {}
                    target_dict['Target'] = th['Target']['Id']
                    target_dict['Health'] = th['TargetHealth']['State']
                    tg_dict['Targets'].append(target_dict)

                alb_dict['TargetGroups'].append(tg_dict)
            alb_list.append(alb_dict)

    return alb_list

def get_all_alb_details():
    ec2_client = boto3.client('ec2')

    regions = ec2_client.describe_regions()['Regions']

    all_alb_details = {}

    for region in regions:
        region_name = region['RegionName']
        albs = get_alb_details(region_name)
        all_alb_details[region_name] = albs

    return all_alb_details

#all_alb_details = get_all_alb_details()
#print(json.dumps(all_alb_details))
if __name__ == "__main__":
    all_alb_details = get_all_alb_details()

    # Save the details to a file named 'alb_data'
    with open('alb_data.json', 'w') as outfile:
        json.dump(all_alb_details, outfile)