import os
import shutil
from datetime import datetime
from dotenv import dotenv_values

# Import the classes from each module
from boto.get_instance_1 import Instance
from boto.get_securitygroup_2 import SecurityGroup
from boto.get_rds_3 import RDS
from boto.get_vpc_4 import VPC
from boto.get_alb_5 import ALB
from boto.get_route_6 import Route
from neo4j_map.update_intelligence_db import UpdateDB

import boto3
# Load environment variables
config = dotenv_values(".env")

# Create a session
session = boto3.Session(profile_name=config['AWS_PROFILE'])

# Define the paths
folder_b = './'
archive_folder = os.path.join(folder_b, 'archive')

# Create archive folder if it doesn't exist
os.makedirs(archive_folder, exist_ok=True)

# Run the scripts from folder boto3 by calling their main methods
def run_scripts():
    instance = Instance(session)
    instance.main()
    
    security_group = SecurityGroup(session)
    security_group.main()
    
    rds = RDS(session)
    rds.main()
    
    vpc = VPC(session)
    vpc.main()
    
    alb = ALB(session)
    alb.main()
    
    route_table = Route(session)
    route_table.main()

# Run the final script from folder neo4j
def run_update_intelligence_db():
    update_db = UpdateDB()
    update_db.main()

# Archive the output files
def archive_files():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_subfolder = os.path.join(archive_folder, f"archive_{timestamp}")
    os.makedirs(archive_subfolder)

    # Define the expected output files
    output_files = [
        'alb_data.json',
        'instance_data.json',
        'rds_data.json',
        'security_group_data.json',
        'vpc_peering_data.json',
        'route_subnet_data.json'
    ]

    # Move the output files to the archive folder
    for output_file in output_files:
        source_file = os.path.join(folder_b, output_file)
        if os.path.exists(source_file):
            shutil.move(source_file, archive_subfolder)
        else:
            print(f"Warning: {source_file} does not exist and will not be archived.")

if __name__ == "__main__":
    run_scripts()  # Run all boto3 scripts
    run_update_intelligence_db()  # Run the final neo4j script
    archive_files()  # Archive the output files
