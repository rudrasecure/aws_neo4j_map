from neo4j import GraphDatabase
from dotenv import dotenv_values
import json
import datetime

config = dotenv_values(".env")

uri = f"neo4j://{config['NEO4J_HOST']}:7687"
driver = GraphDatabase.driver(uri, auth=(config['NEO4J_USER'], config['NEO4J_PASS']))

def add_data_to_neo4j(instance_data, security_group_data, lb_data, rds_data, peering_data):
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
            MERGE (su:Subnet {id: instance.`Subnet ID`})
            MERGE (i:Instance {aws_hostname: instance.Hostname, private_ip: instance.`Internal IP`, public_ip: COALESCE(instance.`External IP`, 'None'), state: instance.State, id:instance.`Instance ID`, name: instance.Tags['Name']})
            MERGE (sn)-[:CONTAINS]->(i)
            MERGE (r)-[:CONTAINS {timestamp: datetime()}]->(i)
            MERGE (sn)-[:CONTAINS]->(r)
            MERGE (i)-[:BELONGS_TO {timestamp: datetime()}]->(v)
            MERGE (i)-[:BELONGS_TO {timestamp: datetime()}]->(su)
            MERGE (sn)-[:CONTAINS]->(v)
            MERGE (sn)-[:CONTAINS]->(su)
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

#To DO : Make the adding of relation between tg_node and instance conditional. Only if the type is instance should this work. Else this will fail
        for region, load_balancers in lb_data.items():
            for lb in load_balancers:
                session.run("""
                MERGE (r:Region {name: $region})
                MERGE (v:VPC {id: $vpc_id})
                WITH r, v
                MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                MERGE (l:LoadBalancer {arn: $load_balancer_arn, dns_name: $dns_name, scheme: $scheme, state: $state, created_time: datetime($created_time)})
                MERGE (sn)-[:CONTAINS]->(l)
                MERGE (l)-[:BELONGS_TO]->(v)
                MERGE (r)-[:CONTAINS]->(l)
                WITH l, sn
                UNWIND $security_groups AS sg_id
                MERGE (sg:SecurityGroup {id: sg_id})
                MERGE (l)-[:BELONGS_TO]->(sg)
                MERGE (sn)-[:CONTAINS]->(sg)
                WITH l, sn
                UNWIND $target_groups AS tg
                MERGE (tg_node:TargetGroup {name: tg.TargetGroupName, arn: tg.TargetGroupArn})
                MERGE (l)-[:CONTAINS]->(tg_node)
                MERGE (sn)-[:CONTAINS]->(tg_node)
                WITH tg, tg_node, sn
                UNWIND tg.Targets AS target
                MATCH (i:Instance {id: target.Target}) 
                MERGE (tg_node)-[:CONTAINS]->(i)
                """, 
                region=region, 
                load_balancer_arn=lb['LoadBalancerArn'], 
                dns_name=lb['DNSName'], 
                vpc_id=lb['VpcId'], 
                state=lb['State']['Code'], 
                scheme=lb['Scheme'], 
                created_time=lb['CreatedTime'], 
                security_groups=lb['SecurityGroups'], 
                target_groups=lb['TargetGroups'], 
                snapshot_id=snapshot_id, 
                version=version)

        for region, instances in rds_data.items():
            session.run("""
            UNWIND $instances AS instance
            MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
            MERGE (r:Region {name: $region})
            MERGE (db:RDSInstance {
                DBInstanceIdentifier: instance.DBInstanceIdentifier,
                DBInstanceStatus: instance.DBInstanceStatus,
                Engine: instance.Engine,
                EngineVersion: instance.EngineVersion,
                DBInstanceClass: instance.DBInstanceClass,
                MasterUsername: instance.MasterUsername,
                VPCId: instance.VPCId,
                MultiAZ: toBoolean(instance.MultiAZ),
                PubliclyAccessible: toBoolean(instance.PubliclyAccessible),
                StorageEncrypted: toBoolean(instance.StorageEncrypted),
                IAMDatabaseAuthenticationEnabled: toBoolean(instance.IAMDatabaseAuthenticationEnabled),
                Endpoint: instance.Endpoint,
                Port: instance.Port,
                BackupRetentionPeriod: instance.BackupRetentionPeriod,
                DBName: COALESCE(instance.DBName, 'Null')
            })
            MERGE (v:VPC {id: instance.VPCId})
            MERGE (db)-[:BELONGS_TO {timestamp: datetime()}]->(v)
            MERGE (db)-[:BELONGS_TO {timestamp: datetime()}]->(r)
            MERGE (sn)-[:CONTAINS]->(db)
            WITH db, instance, sn
            UNWIND instance.VpcSecurityGroups AS vpc_sg
            MERGE (sg:SecurityGroup {id: vpc_sg.VpcSecurityGroupId})
            MERGE (db)-[:BELONGS_TO {timestamp: datetime()}]->(sg)
            MERGE (sn)-[:CONTAINS]->(sg)
            """, snapshot_id=snapshot_id, region=region, instances=instances)

        for connections in peering_data.values():
            session.run("""
            UNWIND $connections AS connection
            MERGE (rv:VPC {id: connection.RequesterVPC})
            MERGE (av:VPC {id: connection.AccepterVPC})
            MERGE (rv)-[p:PEERED_TO {id: connection.PeeringConnectionId, status: connection.Status, timestamp: datetime()}]->(av)
            WITH p, connection
            UNWIND keys(connection.Tags) AS tag_key
            SET p.tag_name=tag_key
            SET p.tag_value=connection.Tags[tag_key]
            """, connections=connections)





try:
    with open('instance_data.json', 'r') as f:
        instance_data = json.load(f)
    with open('security_group_data.json') as f:
        security_group_data = json.load(f)
    with open('alb_data.json', 'r') as f:
        lb_data = json.load(f)
    with open('rds_data.json', 'r') as f:
        rds_data = json.load(f)
    with open('vpc_peering_data.json', 'r') as f:
        peering_data = json.load(f)

except json.JSONDecodeError as e:
    print('Error in JSON decoding:', e)
    faulty_part = open('instances_15062023.json', 'r').read()[e.doc:e.pos]
    print('Faulty part:', faulty_part)

add_data_to_neo4j(instance_data, security_group_data, lb_data, rds_data, peering_data)

driver.close()