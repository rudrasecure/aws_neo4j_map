#!/usr/bin/env python3
import json
import boto3
# import os
# from dotenv import dotenv_values

class ALB:
    def __init__(self, session):
        self.session = session

    def get_alb_details(self, region):
        client = self.session.client('elbv2', region_name=region)

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

                # Get listeners for the load balancer
                try:
                    listeners_response = client.describe_listeners(
                        LoadBalancerArn=alb['LoadBalancerArn'])

                    alb_dict['Listeners'] = []
                    for listener in listeners_response['Listeners']:
                        listener_dict = {}
                        listener_dict['ListenerArn'] = listener['ListenerArn']
                        listener_dict['Port'] = listener['Port']
                        listener_dict['Protocol'] = listener['Protocol']

                        # Add SSL policy if it exists
                        if 'SslPolicy' in listener:
                            listener_dict['SslPolicy'] = listener['SslPolicy']

                        # Get default actions
                        listener_dict['DefaultActions'] = listener['DefaultActions']

                        # Get rules for this listener
                        try:
                            rules_response = client.describe_rules(
                                ListenerArn=listener['ListenerArn'])

                            listener_dict['Rules'] = []
                            for rule in rules_response['Rules']:
                                rule_dict = {}
                                rule_dict['RuleArn'] = rule['RuleArn']
                                rule_dict['Priority'] = rule['Priority']
                                rule_dict['Conditions'] = rule['Conditions']
                                rule_dict['Actions'] = rule['Actions']
                                rule_dict['IsDefault'] = rule['IsDefault']
                                listener_dict['Rules'].append(rule_dict)

                        except Exception as e:
                            print(f"Error getting rules for listener {listener['ListenerArn']}: {e}")
                            listener_dict['Rules'] = []

                        alb_dict['Listeners'].append(listener_dict)

                except Exception as e:
                    print(f"Error getting listeners for ALB {alb['LoadBalancerArn']}: {e}")
                    alb_dict['Listeners'] = []

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

    def get_all_alb_details(self):
        ec2_client = self.session.client('ec2')

        regions = ec2_client.describe_regions()['Regions']

        all_alb_details = {}

        for region in regions:
            region_name = region['RegionName']
            albs = self.get_alb_details(region_name)
            all_alb_details[region_name] = albs

        return all_alb_details

    def main(self):
        all_alb_details = self.get_all_alb_details()

        # Save the details to a file named 'alb_data.json'
        with open('alb_data.json', 'w') as outfile:
            json.dump(all_alb_details, outfile)

# def get_aws_profiles():
#     config = dotenv_values(".env")
#     return [value for key, value in config.items() if key.startswith("AWS_PROFILE")]

# if __name__ == "__main__":
#     import argparse

#     parser = argparse.ArgumentParser(description="Extract ALB data from AWS profiles")
#     parser.add_argument("--profile", type=str, help="Run for specific AWS profile")
#     parser.add_argument("--available", action="store_true", help="Show available AWS profiles")
#     parser.add_argument("--all", action="store_true", help="Run for all profiles")
#     args = parser.parse_args()

#     aws_profiles = get_aws_profiles()

#     if args.available:
#         print("Available AWS profiles in .env:")
#         for profile in aws_profiles:
#             print(f" - {profile}")
#         exit(0)

#     if args.profile:
#         if args.profile not in aws_profiles:
#             print(f"Error: '{args.profile}' not found in .env AWS_PROFILE entries.")
#             exit(1)
#         profiles_to_run = [args.profile]
#     elif args.all:
#         profiles_to_run = aws_profiles
#     else:
#         parser.print_help()
#         exit(1)

#     for profile in profiles_to_run:
#         print(f"\n--- Running ALB extraction for AWS profile: {profile} ---")
#         try:
#             session = boto3.Session(profile_name=profile)
#             alb_extractor = ALB(session)
#             alb_extractor.main()
#             print(f"ALB data saved to alb_data.json for profile: {profile}")
#         except Exception as e:
#             print(f"Error running ALB extraction for profile {profile}: {e}")
