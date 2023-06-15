# AWS Neo4j Mapper
Maps AWS topology in Neo4J 

## Goals
Keeping track of security operations in a large environment demands up to date contextual information at hand, on demand.
The purpose of this repo is to keep up-to-date context on an AWS environment. This documentation will contain certain sample queries that can be run on neo4j.

## Data capture
There are currently, two sources of data that are brought into this context. 
1.  Iterating through regions with  boto3.resource('ec2', region_name=region).instances.all()
2.  Iterating through regions with  boto3.client('ec2', region_name=region).describe_security_groups()

Separate scripts are run which gather the above details in a JSON response. The Security Group ID is a part of the first response. Using that, we build a connected graph tying in a number of elements


## Data and relationships

We are preserving temporal data; these scripts are designed to be run at periodic intervals and capture the entire state of the topology at various time intervals. During a security investigation, this will give us invaluable insights into what the state or context was at a particular point in time. During incident response, threat hunting, and  gap assessments - this is a powerful tool
The temporal element is brought in by creating a "Snapshot" Label node. (Snapshot)-[:CONTAINS]->(Other nodes). In this manner, we can match on Snapshots and search for temporal context

### Here are some of the node types

(sn:Snapshot): Represents a snapshot in your system.
(r:Region {name: $region}): Represents a region in the AWS environment.
(v:VPC {id: instance.VPC}): Represents a VPC (Virtual Private Cloud) in the AWS environment, identified by its ID.
(su:Subnet {id: instance.'Subnet ID'}): Represents a subnet in the AWS environment, identified by its ID.
(i:Instance {aws_hostname: instance.Hostname, private_ip: instance.'Internal IP', public_ip: COALESCE(instance.'External IP', 'None'), state: instance.State}): Represents an EC2 instance in AWS.
(s:SecurityGroup {id: sg.GroupId, name: sg.GroupName}): Represents a security group in the AWS environment.
(t:Tag {name: tag_key, value: instance.Tags[tag_key]}): Represents a tag attached to an instance.

(i:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')}): Represents an IP Range in the AWS environment.
(o:IPRange {cidr: ip_range.CidrIp, description: COALESCE(ip_range.Description, 'No description available')}): Another representation of an IP Range (for outbound rules) in the AWS environment.

### Here are the Relationships

(sn)-[:CONTAINS]->(i): The snapshot includes the information about the EC2 instance.
(r)-[:CONTAINS {timestamp: datetime()}]->(i): The AWS region includes the EC2 instance, and this relationship is timestamped, which gives you information about when this relationship was true.
(sn)-[:CONTAINS]->(r): The snapshot includes the information about the AWS region.
(i)-[:BELONGS_TO {timestamp: datetime()}]->(v): The EC2 instance belongs to a specific VPC. This relationship is also timestamped, meaning that the instance belonged to this VPC at a specific time.
(i)-[:BELONGS_TO {timestamp: datetime()}]->(su): Similarly, the EC2 instance belongs to a specific subnet at a particular time.
(sn)-[:CONTAINS]->(v): The snapshot includes the information about the VPC.
(sn)-[:CONTAINS]->(su): The snapshot includes the information about the subnet.
(i)-[:BELONGS_TO {timestamp: datetime()}]->(s): The EC2 instance belongs to a particular security group at a certain time.
(sn)-[:CONTAINS]->(s): The snapshot includes the information about the security group.
(i)-[:TAGGED {timestamp: datetime()}]->(t): The EC2 instance is tagged with a specific tag at a certain time.
(sn)-[:CONTAINS]->(t): The snapshot includes the information about the tag.


(r)-[:HAS_SECURITYGROUP {timestamp: datetime()}]->(s): An AWS region has a specific security group at a particular time.
(i)-[:ALLOWED {timestamp: datetime(), protocol: inbound.IpProtocol, fromPort: COALESCE(inbound.FromPort, 'Not specified'), toPort: COALESCE(inbound.ToPort, 'Not specified')}]->(s): An IP range is allowed to access the security group according to specific inbound rules. This relationship is timestamped to know when these rules were in effect.
(s)-[:ALLOWED {timestamp: datetime(), protocol: outbound.IpProtocol, fromPort: COALESCE(outbound.FromPort, 'Not specified'), toPort: COALESCE(outbound.ToPort, 'Not specified')}]->(o): A security group allows specific outbound rules to an IP range, which are captured in this relationship, along with a timestamp to know when these rules were in effect.
In essence, these relationships define how different components in the AWS environment relate to each other and how they evolve over time.

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
```

```
#Find all IP ranges/port/protocol that are allowed egress to a particular instance
MATCH (i:Instance {private_ip:"192.168.143.68"})-[b]-(sg:SecurityGroup)-[a:ALLOWED]->(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol
#Same, but shows which security group is the cause of the allowed traffic
MATCH (i:Instance {private_ip:"192.168.143.68"})-[b]-(sg:SecurityGroup)-[a:ALLOWED]->(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol,sg.name 
```


```
#Find all IP ranges/port/protocol that are allowed ingress to a particular instance
MATCH (i:Instance {private_ip:"192.168.143.68"})-[b]-(sg:SecurityGroup)<-[a:ALLOWED]-(ip:IPRange) return ip.cidr,a.fromPort,a.toPort,a.protocol
```

### Putting it into practise
We need to create these queries as a part of a python script that runs as a cron and write to a JSONL file. Wazuh can tail this file and import the logs.
Shuffler + Wazuh can be combined with this to write complex corelated rules that alert upon a very complex combination of scenarios and gaps that  could be causes for security incidents.
