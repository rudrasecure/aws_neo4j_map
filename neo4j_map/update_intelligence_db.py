from neo4j import GraphDatabase
from dotenv import dotenv_values
import json
import datetime

class UpdateDB:
    def __init__(self,db_name):
        self.config = dotenv_values(".env")
        self.uri = f"bolt://{self.config['NEO4J_HOST']}:{self.config['NEO4J_PORT']}"
        self.driver = GraphDatabase.driver(self.uri, auth=(self.config['NEO4J_USER'], self.config['NEO4J_PASS']))
        self.db_name = f"db-{db_name}"

    def create_database(self):
        with self.driver.session() as session:
            result = session.run("SHOW DATABASES")
            db_exists = any(record["name"] == self.db_name for record in result)
            
            if not db_exists:
                session.run(f"CREATE DATABASE `{self.db_name}`")
                print(f"Created database: {self.db_name}")
            else:
                print(f"Database {self.db_name} already exists")

    def add_data_to_neo4j(self,instance_data, security_group_data, lb_data, rds_data, peering_data, route_data):
        with self.driver.session(database=self.db_name) as session:
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
            
            vpc_cidr = []
            for connections in peering_data.values():
                for connection in connections:
                    vpc_cidr_map = {
                    'VpcId': connection['VpcId'],
                    'CidrBlock': connection['CidrBlock']
                    }
                    vpc_cidr.append(vpc_cidr_map)
            
                for vpc_data in vpc_cidr:
                    session.run("""
                        UNWIND $connections AS connection
                        UNWIND connection.PeeringConnections AS pc
                        MERGE (v:VPC {id: $vpc_id})
                        ON CREATE SET v.cidr = $cidr_block,
                                     v.created_date = datetime(),
                                     v.snapshot_version = $version
                        ON MATCH SET v.cidr = $cidr_block,
                                    v.modified_date = datetime(),
                                    v.snapshot_version = $version
                        WITH v, connection
                        UNWIND keys(connection.Tags) AS tag_key
                        CALL apoc.create.setProperty(v, tag_key, connection.Tags[tag_key]) YIELD node
                        RETURN v
                    """, vpc_id=vpc_data['VpcId'], cidr_block=vpc_data['CidrBlock'], connections=connections, version=version)

            for region, instances in instance_data.items():
                session.run("""
                UNWIND $instances AS instance
                MERGE (r:Region {name: $region})
                ON CREATE SET r.created_date = datetime(),
                               r.snapshot_version = $version
                ON MATCH SET r.modified_date = datetime(),
                              r.snapshot_version = $version
                WITH r, instance
                MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                MERGE (v:VPC {id: instance.VPC})
                ON CREATE SET v.created_date = datetime(),
                               v.snapshot_version = $version
                ON MATCH SET v.modified_date = datetime(),
                              v.snapshot_version = $version
                MERGE (su:Subnet {id: instance.`Subnet ID`})
                ON CREATE SET su.created_date = datetime(),
                                su.snapshot_version = $version
                ON MATCH SET su.modified_date = datetime(),
                              su.snapshot_version = $version
                MERGE (v)-[vc:CONTAINS]->(su)
                ON CREATE SET vc.created_date = datetime(),
                               vc.snapshot_version = $version
                ON MATCH SET vc.modified_date = datetime(),
                              vc.snapshot_version = $version
                MERGE (i:Instance {id: instance.`Instance ID`})
                ON CREATE SET 
                    i.aws_hostname = instance.Hostname,
                    i.private_ip = instance.`Internal IP`,
                    i.public_ip = COALESCE(instance.`External IP`, 'None'),
                    i.state = instance.State,
                    i.created_date = datetime(),
                    i.snapshot_version = $version
                ON MATCH SET
                    i.aws_hostname = instance.Hostname,
                    i.private_ip = instance.`Internal IP`,
                    i.public_ip = COALESCE(instance.`External IP`, 'None'),
                    i.state = instance.State,
                    i.modified_date = datetime(),
                    i.snapshot_version = $version
                MERGE (sn)-[:CONTAINS]->(i)
                MERGE (sn)-[:CONTAINS]->(r)
                
                // Use a unique relationship with created/modified dates
                MERGE (i)-[rel:BELONGS_TO]->(su)
                ON CREATE SET rel.created_date = datetime(),
                               rel.snapshot_version = $version
                ON MATCH SET rel.modified_date = datetime(),
                              rel.snapshot_version = $version
                
                MERGE (sn)-[:CONTAINS]->(v)
                MERGE (r)-[:CONTAINS]->(v)
                MERGE (sn)-[:CONTAINS]->(su)
                WITH sn, i, instance
                UNWIND instance.`Security Groups` AS sg
                MERGE (s:SecurityGroup {id: sg.GroupId, name: sg.GroupName})
                ON CREATE SET s.created_date = datetime(),
                               s.snapshot_version = $version
                ON MATCH SET s.modified_date = datetime(),
                              s.snapshot_version = $version
                
                // Use a unique relationship with created/modified dates
                MERGE (i)-[sgRel:BELONGS_TO]->(s)
                ON CREATE SET sgRel.created_date = datetime(),
                               sgRel.snapshot_version = $version
                ON MATCH SET sgRel.modified_date = datetime(),
                              sgRel.snapshot_version = $version
                
                MERGE (sn)-[:CONTAINS]->(s)
                WITH sn, i, instance
                UNWIND keys(instance.Tags) AS tag_key
                CALL apoc.create.setProperty(i, tag_key, instance.Tags[tag_key]) YIELD node
                RETURN i
                """, snapshot_id=snapshot_id, region=region, instances=instances, vpc_cidr=vpc_cidr, version=version)
            
            for routes in route_data.values():
                for route in routes:
                    subnet_id = route['SubnetId']
                    subnet_cidr = route['CidrBlock']
                    route_tables = route['RouteTables']

                    for route_table in route_tables:
                        route_table_id = route_table["RouteTableId"]
                        routes = route_table["Routes"]
                        destination_cidrs = [route["DestinationCidrBlock"] for route in routes if "DestinationCidrBlock" in route]
                        gateway_ids = [route.get("GatewayId") for route in routes if "GatewayId" in route]
                        session.run("""
                        MERGE (rt:RouteTable {id: $route_table_id})
                        ON CREATE SET
                            rt.destinationCidrs = $destination_cidrs,
                            rt.gatewayIds = $gateway_ids,
                            rt.created_date = datetime(),
                            rt.snapshot_version = $version
                        ON MATCH SET
                            rt.destinationCidrs = $destination_cidrs,
                            rt.gatewayIds = $gateway_ids,
                            rt.modified_date = datetime(),
                            rt.snapshot_version = $version
                        WITH rt, $subnet_id AS subnet_id, $subnet_cidr AS cidr
                        MERGE (su:Subnet {id: subnet_id})
                        SET su.CidrBlock = cidr,
                            su.snapshot_version = $version
                        MERGE (su)-[hrt:HAS_ROUTE_TABLE]->(rt)
                        ON CREATE SET hrt.created_date = datetime(),
                                       hrt.snapshot_version = $version
                        ON MATCH SET hrt.modified_date = datetime(),
                                      hrt.snapshot_version = $version
                        WITH rt
                        UNWIND $route_table AS rtable
                        UNWIND keys(rtable.Tags) AS tag_key
                        CALL apoc.create.setProperty(rt, tag_key, rtable.Tags[tag_key]) YIELD node
                        RETURN rt
                        """, route_table=route_table, subnet_id=subnet_id, subnet_cidr=subnet_cidr, 
                             route_table_id=route_table_id, destination_cidrs=destination_cidrs, 
                             gateway_ids=gateway_ids, version=version)
            
                
            for region, security_groups in security_group_data.items():
                session.run("""
                UNWIND $security_groups AS sg
                MERGE (r:Region {name: $region})
                ON CREATE SET r.created_date = datetime(),
                               r.snapshot_version = $version
                ON MATCH SET r.modified_date = datetime(),
                              r.snapshot_version = $version
                WITH r, sg
                MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                MERGE (s:SecurityGroup {id: sg.GroupId, name: sg.GroupName})
                ON CREATE SET 
                    s.description = COALESCE(sg.Description, 'None'),
                    s.created_date = datetime(),
                    s.snapshot_version = $version
                ON MATCH SET 
                    s.description = COALESCE(sg.Description, 'None'),
                    s.modified_date = datetime(),
                    s.snapshot_version = $version
                MERGE (sn)-[:CONTAINS]->(s)
                WITH sn, sg, s
                UNWIND sg.InboundRules AS inbound
                UNWIND inbound.IpRanges AS ip_range
                MERGE (i:IPRange {cidr: ip_range.CidrIp})
                ON CREATE SET 
                    i.description = COALESCE(ip_range.Description, 'No description available'),
                    i.created_date = datetime(),
                    i.snapshot_version = $version
                ON MATCH SET 
                    i.description = COALESCE(ip_range.Description, 'No description available'),
                    i.modified_date = datetime(),
                    i.snapshot_version = $version
                
                // Use a composite key for the relationship based on protocol and ports
                MERGE (i)-[inRel:ALLOWED_IN {
                    protocol: inbound.IpProtocol, 
                    fromPort: COALESCE(inbound.FromPort, 'Not specified'), 
                    toPort: COALESCE(inbound.ToPort, 'Not specified')
                }]->(s)
                ON CREATE SET inRel.created_date = datetime(),
                               inRel.snapshot_version = $version
                ON MATCH SET inRel.modified_date = datetime(),
                              inRel.snapshot_version = $version
                
                WITH sn, sg, s
                UNWIND sg.OutboundRules AS outbound
                UNWIND outbound.IpRanges AS ip_range
                MERGE (o:IPRange {cidr: ip_range.CidrIp})
                ON CREATE SET 
                    o.description = COALESCE(ip_range.Description, 'No description available'),
                    o.created_date = datetime(),
                    o.snapshot_version = $version
                ON MATCH SET 
                    o.description = COALESCE(ip_range.Description, 'No description available'),
                    o.modified_date = datetime(),
                    o.snapshot_version = $version
                
                // Use a composite key for the relationship based on protocol and ports
                MERGE (s)-[outRel:ALLOWED_OUT {
                    protocol: outbound.IpProtocol, 
                    fromPort: COALESCE(outbound.FromPort, 'Not specified'), 
                    toPort: COALESCE(outbound.ToPort, 'Not specified')
                }]->(o)
                ON CREATE SET outRel.created_date = datetime(),
                               outRel.snapshot_version = $version
                ON MATCH SET outRel.modified_date = datetime(),
                              outRel.snapshot_version = $version
                
                MERGE (sn)-[:CONTAINS]->(s)
                """, snapshot_id=snapshot_id, region=region, security_groups=security_groups, version=version)

            for region, load_balancers in lb_data.items():
                for lb in load_balancers:
                    # Create LoadBalancer, VPC, Region, and SecurityGroup relationships
                    session.run("""
                    MERGE (r:Region {name: $region})
                    ON CREATE SET r.created_date = datetime(),
                                   r.snapshot_version = $version
                    ON MATCH SET r.modified_date = datetime(),
                                  r.snapshot_version = $version
                    MERGE (v:VPC {id: $vpc_id})
                    ON CREATE SET v.created_date = datetime(),
                                   v.snapshot_version = $version
                    ON MATCH SET v.modified_date = datetime(),
                                  v.snapshot_version = $version
                    WITH r, v
                    MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                    MERGE (l:LoadBalancer {arn: $load_balancer_arn, dns_name: $dns_name})
                    ON CREATE SET
                        l.scheme = $scheme,
                        l.state = $state,
                        l.created_time = datetime($created_time),
                        l.created_date = datetime(),
                        l.snapshot_version = $version
                    ON MATCH SET
                        l.scheme = $scheme,
                        l.state = $state,
                        l.modified_date = datetime(),
                        l.snapshot_version = $version
                    MERGE (sn)-[:CONTAINS]->(l)
                    MERGE (l)-[bt:BELONGS_TO]->(v)
                    ON CREATE SET bt.created_date = datetime(),
                                   bt.snapshot_version = $version
                    ON MATCH SET bt.modified_date = datetime(),
                                  bt.snapshot_version = $version
                    WITH l, sn
                    UNWIND $security_groups AS sg_id
                    MERGE (sg:SecurityGroup {id: sg_id})
                    ON CREATE SET sg.created_date = datetime(),
                                   sg.snapshot_version = $version
                    ON MATCH SET sg.modified_date = datetime(),
                                  sg.snapshot_version = $version
                    MERGE (l)-[bts:BELONGS_TO]->(sg)
                    ON CREATE SET bts.created_date = datetime(),
                                   bts.snapshot_version = $version
                    ON MATCH SET bts.modified_date = datetime(),
                                  bts.snapshot_version = $version
                    MERGE (sn)-[:CONTAINS]->(sg)
                    """,
                    region=region,
                    load_balancer_arn=lb['LoadBalancerArn'],
                    dns_name=lb['DNSName'],
                    vpc_id=lb['VpcId'],
                    state=lb['State']['Code'],
                    scheme=lb['Scheme'],
                    created_time=lb['CreatedTime'],
                    security_groups=lb['SecurityGroups'],
                    snapshot_id=snapshot_id,
                    version=version)

                    # Create Listeners and their relationships
                    if 'Listeners' in lb:
                        for listener in lb['Listeners']:
                            session.run("""
                            MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                            MATCH (l:LoadBalancer {arn: $load_balancer_arn})
                            MERGE (listener:Listener {arn: $listener_arn})
                            ON CREATE SET
                                listener.port = $port,
                                listener.protocol = $protocol,
                                listener.ssl_policy = $ssl_policy,
                                listener.created_date = datetime(),
                                listener.snapshot_version = $version
                            ON MATCH SET
                                listener.port = $port,
                                listener.protocol = $protocol,
                                listener.ssl_policy = $ssl_policy,
                                listener.modified_date = datetime(),
                                listener.snapshot_version = $version
                            MERGE (sn)-[:CONTAINS]->(listener)
                            MERGE (l)-[has_listener:HAS_LISTENER]->(listener)
                            ON CREATE SET has_listener.created_date = datetime(),
                                           has_listener.snapshot_version = $version
                            ON MATCH SET has_listener.modified_date = datetime(),
                                          has_listener.snapshot_version = $version
                            """,
                            snapshot_id=snapshot_id,
                            load_balancer_arn=lb['LoadBalancerArn'],
                            listener_arn=listener['ListenerArn'],
                            port=listener['Port'],
                            protocol=listener['Protocol'],
                            ssl_policy=listener.get('SslPolicy', 'None'),
                            version=version)

                            # Create Rules for each Listener with relationships to Target Groups
                            if 'Rules' in listener:
                                for rule in listener['Rules']:
                                    # Extract target group ARNs from rule actions
                                    target_group_arns = []
                                    for action in rule.get('Actions', []):
                                        if action.get('Type') == 'forward':
                                            if 'TargetGroupArn' in action:
                                                target_group_arns.append(action['TargetGroupArn'])
                                            elif 'ForwardConfig' in action:
                                                for tg_config in action['ForwardConfig'].get('TargetGroups', []):
                                                    target_group_arns.append(tg_config['TargetGroupArn'])

                                    # Create relationships from Listener to Target Groups via Rules
                                    for tg_arn in target_group_arns:
                                        session.run("""
                                        MATCH (listener:Listener {arn: $listener_arn})
                                        MERGE (tg:TargetGroup {arn: $target_group_arn})
                                        ON CREATE SET tg.created_date = datetime(),
                                                       tg.snapshot_version = $version
                                        ON MATCH SET tg.modified_date = datetime(),
                                                      tg.snapshot_version = $version
                                        MERGE (listener)-[routes_to:ROUTES_TO {
                                            rule_arn: $rule_arn,
                                            priority: $priority,
                                            is_default: $is_default,
                                            conditions: $conditions,
                                            actions: $actions
                                        }]->(tg)
                                        ON CREATE SET routes_to.created_date = datetime(),
                                                       routes_to.snapshot_version = $version
                                        ON MATCH SET routes_to.modified_date = datetime(),
                                                      routes_to.snapshot_version = $version
                                        """,
                                        listener_arn=listener['ListenerArn'],
                                        target_group_arn=tg_arn,
                                        rule_arn=rule['RuleArn'],
                                        priority=str(rule['Priority']),
                                        is_default=rule['IsDefault'],
                                        conditions=json.dumps(rule.get('Conditions', [])),
                                        actions=json.dumps(rule.get('Actions', [])),
                                        version=version)

                    # Create TargetGroups and their relationships to instances
                    for tg in lb['TargetGroups']:
                        session.run("""
                        MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                        MERGE (tg_node:TargetGroup {name: $target_group_name, arn: $target_group_arn})
                        ON CREATE SET tg_node.created_date = datetime(),
                                       tg_node.snapshot_version = $version
                        ON MATCH SET tg_node.modified_date = datetime(),
                                      tg_node.snapshot_version = $version
                        MERGE (sn)-[:CONTAINS]->(tg_node)
                        WITH tg_node, sn
                        UNWIND $targets AS target
                        // Only create relationship if instance exists
                        OPTIONAL MATCH (i:Instance {id: target.Target})
                        WITH tg_node, i, target, sn WHERE i IS NOT NULL
                        MERGE (tg_node)-[cti:CONTAINS {health: target.Health}]->(i)
                        ON CREATE SET cti.created_date = datetime(),
                                       cti.snapshot_version = $version
                        ON MATCH SET cti.health = target.Health,
                                      cti.modified_date = datetime(),
                                      cti.snapshot_version = $version
                        """,
                        snapshot_id=snapshot_id,
                        target_group_name=tg['TargetGroupName'],
                        target_group_arn=tg['TargetGroupArn'],
                        targets=tg['Targets'],
                        version=version)

            for region, instances in rds_data.items():
                session.run("""
                UNWIND $instances AS instance
                MATCH (sn:Snapshot) WHERE ID(sn) = $snapshot_id
                MERGE (r:Region {name: $region})
                ON CREATE SET r.created_date = datetime(),
                               r.snapshot_version = $version
                ON MATCH SET r.modified_date = datetime(),
                              r.snapshot_version = $version
                MERGE (db:RDSInstance {DBInstanceIdentifier: instance.DBInstanceIdentifier})
                ON CREATE SET
                    db.DBInstanceStatus = instance.DBInstanceStatus,
                    db.Engine = instance.Engine,
                    db.EngineVersion = instance.EngineVersion,
                    db.DBInstanceClass = instance.DBInstanceClass,
                    db.MasterUsername = instance.MasterUsername,
                    db.VPCId = instance.VPCId,
                    db.MultiAZ = toBoolean(instance.MultiAZ),
                    db.PubliclyAccessible = toBoolean(instance.PubliclyAccessible),
                    db.StorageEncrypted = toBoolean(instance.StorageEncrypted),
                    db.IAMDatabaseAuthenticationEnabled = toBoolean(instance.IAMDatabaseAuthenticationEnabled),
                    db.Endpoint = instance.Endpoint,
                    db.Port = instance.Port,
                    db.BackupRetentionPeriod = instance.BackupRetentionPeriod,
                    db.DBName = COALESCE(instance.DBName, 'Null'),
                    db.created_date = datetime(),
                    db.snapshot_version = $version
                ON MATCH SET
                    db.DBInstanceStatus = instance.DBInstanceStatus,
                    db.Engine = instance.Engine,
                    db.EngineVersion = instance.EngineVersion,
                    db.DBInstanceClass = instance.DBInstanceClass,
                    db.MasterUsername = instance.MasterUsername,
                    db.VPCId = instance.VPCId,
                    db.MultiAZ = toBoolean(instance.MultiAZ),
                    db.PubliclyAccessible = toBoolean(instance.PubliclyAccessible),
                    db.StorageEncrypted = toBoolean(instance.StorageEncrypted),
                    db.IAMDatabaseAuthenticationEnabled = toBoolean(instance.IAMDatabaseAuthenticationEnabled),
                    db.Endpoint = instance.Endpoint,
                    db.Port = instance.Port,
                    db.BackupRetentionPeriod = instance.BackupRetentionPeriod,
                    db.DBName = COALESCE(instance.DBName, 'Null'),
                    db.modified_date = datetime(),
                    db.snapshot_version = $version
                MERGE (v:VPC {id: instance.VPCId})
                ON CREATE SET v.created_date = datetime(),
                               v.snapshot_version = $version
                ON MATCH SET v.modified_date = datetime(),
                              v.snapshot_version = $version
                
                // Use a unique relationship with created/modified dates
                MERGE (db)-[vpcRel:BELONGS_TO]->(v)
                ON CREATE SET vpcRel.created_date = datetime(),
                               vpcRel.snapshot_version = $version
                ON MATCH SET vpcRel.modified_date = datetime(),
                              vpcRel.snapshot_version = $version
                
                MERGE (sn)-[:CONTAINS]->(db)
                WITH db, instance, sn
                UNWIND instance.VpcSecurityGroups AS vpc_sg
                MERGE (sg:SecurityGroup {id: vpc_sg.VpcSecurityGroupId})
                ON CREATE SET sg.created_date = datetime(),
                               sg.snapshot_version = $version
                ON MATCH SET sg.modified_date = datetime(),
                              sg.snapshot_version = $version
                
                // Use a unique relationship with created/modified dates
                MERGE (db)-[sgRel:BELONGS_TO]->(sg)
                ON CREATE SET sgRel.created_date = datetime(),
                               sgRel.snapshot_version = $version
                ON MATCH SET sgRel.modified_date = datetime(),
                              sgRel.snapshot_version = $version
                
                MERGE (sn)-[:CONTAINS]->(sg)
                """, snapshot_id=snapshot_id, region=region, instances=instances, version=version)

            for connections in peering_data.values():
                session.run("""
                UNWIND $connections AS connection
                UNWIND connection.PeeringConnections AS pc
                MATCH(rv:VPC {id:pc.RequesterVpcId})
                MATCH (av:VPC {id: pc.AccepterVpcId})
                
                // Use MERGE with a unique identifier (the peering connection ID)
                MERGE (rv)-[p:PEERED_TO {id: COALESCE(pc.PeeringConnectionId,'None')}]->(av)
                ON CREATE SET 
                    p.status = COALESCE(pc.Status,'None'),
                    p.created_date = datetime(),
                    p.snapshot_version = $version
                ON MATCH SET 
                    p.status = COALESCE(pc.Status,'None'),
                    p.modified_date = datetime(),
                    p.snapshot_version = $version
                
                WITH pc, p
                UNWIND keys(pc.Tags) AS tag_key
                CALL apoc.create.setRelProperty(p, tag_key, pc.Tags[tag_key]) YIELD rel
                RETURN p
                """, connections=connections, version=version)

    def main(self):
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
            with open('route_subnet_data.json','r') as f:
                route_data = json.load(f)

        except json.JSONDecodeError as e:
            print('Error in JSON decoding:', e)
            faulty_part = open('instances_15062023.json', 'r').read()[e.doc:e.pos]
            print('Faulty part:', faulty_part)

        self.create_database()
        self.add_data_to_neo4j(instance_data=instance_data, security_group_data=security_group_data, lb_data=lb_data, rds_data=rds_data, peering_data=peering_data, route_data=route_data)

        self.driver.close()