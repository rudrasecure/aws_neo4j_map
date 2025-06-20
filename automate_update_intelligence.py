import os
import shutil
import argparse
from datetime import datetime
from dotenv import dotenv_values

import boto3
from boto.get_instance_1 import Instance
from boto.get_securitygroup_2 import SecurityGroup
from boto.get_rds_3 import RDS
from boto.get_vpc_4 import VPC
from boto.get_alb_5 import ALB
from boto.get_route_6 import Route
from neo4j_map.update_intelligence_db import UpdateDB

# Load environment variables
config = dotenv_values(".env")

# Define the paths
folder_b = './'
archive_folder = os.path.join(folder_b, 'archive')
os.makedirs(archive_folder, exist_ok=True)

def run_scripts(session):
    Instance(session).main()
    SecurityGroup(session).main()
    RDS(session).main()
    VPC(session).main()
    ALB(session).main()
    Route(session).main()

def run_update_intelligence_db(db_name):
    UpdateDB(db_name=db_name).main()

def archive_files(profile_name):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_subfolder = os.path.join(archive_folder, f"{profile_name}_archive_{timestamp}")
    os.makedirs(archive_subfolder)

    output_files = [
        'alb_data.json',
        'instance_data.json',
        'rds_data.json',
        'security_group_data.json',
        'vpc_peering_data.json',
        'route_subnet_data.json'
    ]

    for output_file in output_files:
        source_file = os.path.join(folder_b, output_file)
        if os.path.exists(source_file):
            shutil.move(source_file, archive_subfolder)
        else:
            print(f"Warning: {source_file} does not exist and will not be archived.")

def get_aws_profiles():
    return [value for key, value in config.items() if key.startswith("AWS_PROFILE")]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run AWS data extraction and update intelligence DB.")
    parser.add_argument("--profile", type=str, help="Run the script for a specific AWS profile.")
    parser.add_argument("--available", action="store_true", help="Show available AWS profiles and exit.")
    args = parser.parse_args()

    aws_profiles = get_aws_profiles()

    if args.available:
        print("Available AWS profiles in .env:")
        for profile in aws_profiles:
            print(f" - {profile}")
        exit(0)

    if args.profile:
        if args.profile not in aws_profiles:
            print(f"Error: '{args.profile}' not found in .env AWS_PROFILE entries.")
            exit(1)
        profiles_to_run = [args.profile]
    else:
        profiles_to_run = aws_profiles

    for profile in profiles_to_run:
        print(f"\n--- Running for AWS profile: {profile} ---\n")
        session = boto3.Session(profile_name=profile)

        run_scripts(session)
        run_update_intelligence_db(db_name=profile)
        archive_files(profile)
