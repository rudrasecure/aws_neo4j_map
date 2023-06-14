from neo4j import GraphDatabase
from dotenv import dotenv_values
import json
import datetime

config = dotenv_values(".env")

uri = f"neo4j://{config['NEO4J_HOST']}:7687"
driver = GraphDatabase.driver(uri, auth=(config['NEO4J_USER'], config['NEO4J_PASS']))

def add_data_to_neo4j(instance_data, security_group_data):
    with driver.session() as session:
        # Check for the highest version number in the Snapshot nodes
        highest_version_result = session.run("MATCH (sn:Snapshot) RETURN max(sn.version) AS highest_version")
        highest_version = highest_version_result.single()[0]
        
        # If there's no highest version found, this is the first snapshot
        if highest_version is None:
            version = 1
        else:
            version = highest_version + 1
        
        # Create a single Snapshot node for this run and get its properties
        snapshot_result = session.run("CREATE (sn:Snapshot {timestamp: datetime(), version: $version}) RETURN ID(sn) AS snapshot_id", version=version)
        snapshot_id = snapshot_result.single()[0]


        for region, instances in instance_data.items():
            session.run("""
            UNWIND $instances AS instance
            MERGE (r:Region {name: $region})
            WITH r, instance
            MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
            MERGE (v:VPC {id: instance.VPC})
            MERGE (i:Instance {aws_hostname: instance.Hostname, private_ip: instance.`Internal IP`, public_ip: COALESCE(instance.`External IP`, 'None')})
            MERGE (sn)-[:CONTAINS]->(i)
            MERGE (r)-[:CONTAINS {timestamp: datetime()}]->(i)
            MERGE (sn)-[:CONTAINS]->(r)
            MERGE (i)-[:BELONGS_TO {timestamp: datetime()}]->(v)
            MERGE (sn)-[:CONTAINS]->(v)
            WITH sn, i, instance
            UNWIND instance.`Security Groups` AS sg
            MERGE (s:SecurityGroup {id: sg.GroupId, name: sg.GroupName})
            MERGE (i)-[:BELONGS_TO {timestamp: datetime()}]->(s)
            MERGE (sn)-[:CONTAINS]->(s)
            WITH sn, i, instance
            UNWIND keys(instance.Tags) AS tag_key
            MERGE (t:Tag {name: tag_key, value: instance.Tags[tag_key]})
            ON CREATE SET t.value = instance.Tags[tag_key]
            MERGE (i)-[:TAGGED {timestamp: datetime()}]->(t)
            MERGE (sn)-[:CONTAINS]->(t)
            """, snapshot_id=snapshot_id, region=region, instances=instances)

        for region, security_groups in security_group_data.items():
            session.run("""
            UNWIND $security_groups AS sg
            MERGE (r:Region {name: $region})
            WITH r, sg
            MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
            MERGE (s:SecurityGroup {id: sg.GroupId, name: sg.GroupName})
            MERGE (r)-[:HAS_SECURITYGROUP {timestamp: datetime()}]->(s)
            MERGE (sn)-[:CONTAINS]->(s)
            WITH sn, sg, s
            UNWIND sg.InboundRules AS inbound
            UNWIND inbound.IpRanges AS ip_range
            MERGE (i:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')})
            MERGE (i)-[:ALLOWED {timestamp: datetime(), protocol: inbound.IpProtocol, fromPort: COALESCE(inbound.FromPort, 'Not specified'), toPort: COALESCE(inbound.ToPort, 'Not specified')}]->(s)
            WITH sn, sg, s
            UNWIND sg.OutboundRules AS outbound
            UNWIND outbound.IpRanges AS ip_range
            MERGE (o:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')})
            MERGE (s)-[:ALLOWED {timestamp: datetime(), protocol: outbound.IpProtocol, fromPort: COALESCE(outbound.FromPort, 'Not specified'), toPort: COALESCE(outbound.ToPort, 'Not specified')}]->(o)
            MERGE (sn)-[:CONTAINS]->(s)
            """, snapshot_id=snapshot_id, region=region, security_groups=security_groups)



try:
    with open('instances_wed_jun14_2023.json', 'r') as f:
        instance_data = json.load(f)
    with open('security_groups_14_june_2023.json') as f:
        security_group_data = json.load(f)
except json.JSONDecodeError as e:
    print('Error in JSON decoding:', e)
    faulty_part = open('instances_wed_jun14_2023.json', 'r').read()[e.doc:e.pos]
    print('Faulty part:', faulty_part)

add_data_to_neo4j(instance_data, security_group_data)

driver.close()