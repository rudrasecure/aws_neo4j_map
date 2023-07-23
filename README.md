# AWS Neo4j Mapper
Maps AWS topology in Neo4J 

## Goals
Keeping track of security operations in a large environment demands up to date contextual information at hand, on demand.
The purpose of this repo is to keep up-to-date context on an AWS environment. This documentation will contain certain sample queries that can be run on neo4j. It can be integrated into any SIEM tooling with a bit of scripting. 

## Access required
In order to make use of the data capture methods listed below, you'll need an IAM user with SecurityAudit and ViewOnlyAccess policies. 

## How to Use

* Setup Neo4j - a docker container setup would be the easiest
* Setup your .env with the creds for Neo4j
* Create a virtualenv and install the requirements
* Run all the scripts in the boto3 folder and redirect the output into a .json file (this can be done on a separate machine - possibly in your AWS environment). Note that the scripts will have to have the above IAM credentials to work
* Run update_intelligence_db.py in the Neo4j folder. You'll need to ensure that the files that you created in the previous step are in the same directory as the script, and ensure that the correct names are referenced at the bottom of this script.

We've kept components loosely coupled so that it can be built into any automation system; as we refine/mature this out, we'll make it easier to run. 

## Blog
https://www.linkedin.com/pulse/cyber-response-context-karan-sajnani 

## Data capture
We're using the AWS API's - accessed via the boto3 SDK for python to pull in all the data. Data sources are pulled currently from the following boto3 functions (this could be out of date so please check by referencing the boto3 folder) 
1.  Iterating through regions with  boto3.resource('ec2', region_name=region).instances.all()
2.  Iterating through regions with  boto3.client('ec2', region_name=region).describe_security_groups()
3.  Iterating through rds instances with RDS.Client.describe_db_instances(**kwargs)
4.  Enumerating VPC Peering connections with EC2.Client.describe_vpc_peering_connections(**kwargs)
5.  Enumerating load balancers with the ElasticLoadBalancingv2.Client.describe_load_balancers(**kwargs)
Separate scripts are run which gather the above details in a JSON response. The Security Group ID is a part of the first response. Using that, we build a connected graph tying in a number of elements


## Data and relationships

We are preserving temporal data; these scripts are designed to be run at periodic intervals and capture the entire state of the topology at various time intervals. During a security investigation, this will give us invaluable insights into what the state or context was at a particular point in time. During incident response, threat hunting, and  gap assessments - this is a powerful tool
The temporal element is brought in by creating a "Snapshot" Label node. (Snapshot)-[:CONTAINS]->(Other nodes). In this manner, we can match on Snapshots and search for temporal context

### Here are some of the node types

* (sn:Snapshot): Represents a snapshot in your system.
* (r:Region {name: $region}): Represents a region in the AWS environment.
* (v:VPC {id: instance.VPC}): Represents a VPC (Virtual Private Cloud) in the AWS environment, identified by its ID.
* (su:Subnet {id: instance.'Subnet ID'}): Represents a subnet in the AWS environment, identified by its ID.
* (i:Instance {aws_hostname: instance.Hostname, private_ip: instance.'Internal IP', public_ip: COALESCE(instance.'External IP', 'None'), state: instance.State}): Represents an EC2 instance in AWS.
* (s:SecurityGroup {id: sg.GroupId, name: sg.GroupName}): Represents a security group in the AWS environment.
* (t:Tag {name: tag_key, value: instance.Tags[tag_key]}): Represents a tag attached to an instance.
* (db:RDSInstance {...}): Represents an RDS instance in the AWS environment, characterized by its DBInstanceIdentifier, DBInstanceStatus, Engine, EngineVersion, DBInstanceClass, MasterUsername, VPCId, MultiAZ, PubliclyAccessible, StorageEncrypted, IAMDatabaseAuthenticationEnabled, Endpoint, Port, BackupRetentionPeriod, and DBName properties.
* (l:LoadBalancer {...}): Represents a load balancer in the AWS environment, characterized by its ARN, DNS name, scheme, state, and creation time properties.
* (tg_node:TargetGroup {...}): Represents a target group in the AWS environment, characterized by its name and ARN properties. A target group serves the upstream of a load balancer. An instance, or a lambda can belong to a target group. The current code only supports instances being behind a target group

* (i:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')}): Represents an IP Range in the AWS environment.
* (o:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')}): Another representation of an IP Range (for outbound rules) in the AWS environment.

### Here are the Relationships

* (sn)-[:CONTAINS]->(i): The snapshot includes the information about the EC2 instance.
* (r)-[:CONTAINS {timestamp: datetime()}]->(i): The AWS region includes the EC2 instance, and this relationship is timestamped, which gives you information about when this relationship was true.
* (sn)-[:CONTAINS]->(r): The snapshot includes the information about the AWS region.
* (i)-[:BELONGS_TO {timestamp: datetime()}]->(v): The EC2 instance belongs to a specific VPC. This relationship is also timestamped, meaning that the instance belonged to this VPC at a specific time.
* (i)-[:BELONGS_TO {timestamp: datetime()}]->(su): Similarly, the EC2 instance belongs to a specific subnet at a particular time.
* (sn)-[:CONTAINS]->(v): The snapshot includes the information about the VPC.
* (sn)-[:CONTAINS]->(su): The snapshot includes the information about the subnet.
* (i)-[:BELONGS_TO {timestamp: datetime()}]->(s): The EC2 instance belongs to a particular security group at a certain time.
* (sn)-[:CONTAINS]->(s): The snapshot includes the information about the security group.
* (i)-[:TAGGED {timestamp: datetime()}]->(t): The EC2 instance is tagged with a specific tag at a certain time.
* (sn)-[:CONTAINS]->(t): The snapshot includes the information about the tag.
* (rv:VPC)-[:PEERED_TO {timestamp: datetime()}]->(av:VPC): Represents a peering relationship between two VPCs, i.e., the requester VPC (rv:VPC) is peered to the accepter VPC (av:VPC). The timestamp indicates when this relationship was added to the database. Tags will indicate the reason for this peering, or the name - through which the reason should be inferable
* (l:LoadBalancer {arn: $load_balancer_arn, dns_name: $dns_name, scheme: $scheme, state: $state, created_time: datetime($created_time)}): Represents a load balancer in the AWS environment. The load balancer is identified by its Amazon Resource Name (ARN), DNS name, scheme (either internet-facing or internal), state (active or inactive), and the time it was created.
* (tg_node:TargetGroup {name: tg.TargetGroupName, arn: tg.TargetGroupArn}): Represents a target group in the AWS environment. The target group is identified by its name and ARN. A target group is used to route requests to one or more registered targets when using a load balancer.



* (r)-[:HAS_SECURITYGROUP {timestamp: datetime()}]->(s): An AWS region has a specific security group at a particular time.
* (i)-[:ALLOWED {timestamp: datetime(), protocol: inbound.IpProtocol, fromPort: COALESCE(inbound.FromPort, 'Not specified'), toPort: COALESCE(inbound.ToPort, 'Not specified')}]->(s): An IP range is allowed to access the security group according to specific inbound rules. This relationship is timestamped to know when these rules were in effect.
* (s)-[:ALLOWED {timestamp: datetime(), protocol: outbound.IpProtocol, fromPort: COALESCE(outbound.FromPort, 'Not specified'), toPort: COALESCE(outbound.ToPort, 'Not specified')}]->(o): A security group allows specific outbound rules to an IP range, which are captured in this relationship, along with a timestamp to know when these rules were in effect.
The direction of the relationship between IPRanges and SecurityGroups determines whether the rule is for ingress or egress traffic
In essence, these relationships define how different components in the AWS environment relate to each other and how they evolve over time.

* (rv)-[p:PEERED_TO {id: connection.PeeringConnectionId, status: connection.Status, timestamp: datetime()}]->(av) : This operation establishes a PEERED_TO relationship between the Requester VPC (rv) and the Acceptor VPC (av). The relationship contains properties such as the Peering Connection ID, its status, and the timestamp when the relationship was created or updated. The relationship also has attributes which are essentially 'tags' on the VPC peering connection - these (hopefully) should explain why the peering exists.


## Insights and sample queries

Here's where the fun begins - some sample queries. Their purpose is mentioned in the comments above them

```
#Find all database servers with unrestricted egress access, return the details of the system and the owner
MATCH (t:Tag)-[]-(i:Instance) 
WHERE  (toLower(t.value) CONTAINS "db" OR toLower(t.value) CONTAINS "database") 
       AND NOT toLower(t.value) CONTAINS "standby" 
WITH i, t
MATCH (i)-[:BELONGS_TO]->(s:SecurityGroup)-[]->(ir:IPRange {cidr:"0.0.0.0/0"}) 
WITH i, t
MATCH (i)-[:TAGGED]-(p:Tag {name:"owner"})   
RETURN DISTINCT(p.value), i.private_ip, t.value


#Find all AWS RDS instances where encryption is off
MATCH (n:RDSInstance {StorageEncrypted:false}) RETURN n
```

```
#Find all IP ranges/port/protocol that are allowed egress to a particular instance
MATCH (i:Instance {private_ip:"192.168.***.***"})-[b]-(sg:SecurityGroup)-[a:ALLOWED]->(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol
#Same, but shows which security group is the cause of the allowed traffic
MATCH (i:Instance {private_ip:"192.168.***.***"})-[b]-(sg:SecurityGroup)-[a:ALLOWED]->(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol,sg.name 
```


```
#Find all IP ranges/port/protocol that are allowed ingress to a particular instance
MATCH (i:Instance {private_ip:"192.168.***.***"})-[b]-(sg:SecurityGroup)<-[a:ALLOWED]-(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol
```

```
#Find which load balancer an instance is connected to the internet by
MATCH (n:Instance {private_ip:'192.168.***.***'})-[]-(t:TargetGroup)-[]-(lb:LoadBalancer) RETURN n,t,lb LIMIT 25
```

### Putting it into practise
We need to create these queries as a part of a python script that runs as a cron and write to a JSONL file. Wazuh can tail this file and import the logs.
Shuffler + Wazuh can be combined with this to write complex corelated rules that alert upon a very complex combination of scenarios and gaps that  could be causes for security incidents.


### To Do 
The Target Group at the moment can only contain an EC2 instance - it needs to be expanded to cater for scenarios where a target group is backended by Lambdas or other AWS elements that can serve a Target Group

## Contributing
We welcome code contributions and ideas.

