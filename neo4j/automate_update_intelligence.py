import os
import subprocess
import shutil
from datetime import datetime

# Define the paths
folder_a = '../boto3/'
folder_b = '../neo4j/'
archive_folder = os.path.join(folder_b, 'archive')
#archive_folder = 'archive'

# Create archive folder if it doesn't exist
os.makedirs(archive_folder, exist_ok=True)

# List of scripts to run from folder b
scripts_folder_a = ['get_instance_1.py', 'get_securitygroup_2.py', 'get_rds_3.py', 'get_vpc_4.py', 'get_alb_5.py', 'get_route_6.py']

# Run scripts from folder boto3
for script in scripts_folder_a:
    script_path = os.path.join(folder_a, script)
    subprocess.run(['python3', script_path])

# Run the final script from folder neo4j
final_script = 'update_intelligence_db.py'
final_script_path = os.path.join(folder_b, final_script)
subprocess.run(['python3', final_script_path])

# Archive the output files
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