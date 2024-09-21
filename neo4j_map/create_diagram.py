from neo4j import GraphDatabase
from dotenv import dotenv_values
from jinja2 import Environment, FileSystemLoader

class AWSDiagramGenerator:
    def __init__(self):
        # Load configuration for Neo4j
        self.config = dotenv_values(".env")
        self.uri = f"neo4j://{self.config['NEO4J_HOST']}:7687"
        self.driver = GraphDatabase.driver(self.uri, auth=(self.config['NEO4J_USER'], self.config['NEO4J_PASS']))
        
        # Set up Jinja2 environment
        self.env = Environment(loader=FileSystemLoader('.'))

    def query_vpcs_and_subnets(self):
        # Query Neo4j for VPCs and subnets
        query = """
        MATCH (v:VPC)-[:CONTAINS]->(su:Subnet)
        RETURN 
            v.id AS vpc_id, 
            v.cidr AS vpc_cidr, 
            collect({
                subnet_id: su.id, 
                subnet_cidr: su.CidrBlock
            }) AS subnets
        """
        with self.driver.session() as session:
            result = session.run(query)
            return result.data()

    def query_subnets_and_instances(self):
        # Query Neo4j for subnets and their associated instances
        query = """
            MATCH (su:Subnet)<-[:BELONGS_TO]-(i:Instance)
            RETURN 
                su.id AS subnet_id, 
                collect({
                    instance_id: i.id,
                    instance_name: i.Name,
                    private_ip: i.private_ip,
                    public_ip: i.public_ip
                }) AS instances
        """
        with self.driver.session() as session:
            result = session.run(query)
            return result.data()

    def correlate_data(self, vpcs_and_subnets, subnets_and_instances):
        # Correlate subnets with their instances
        for vpc in vpcs_and_subnets:
            for subnet in vpc['subnets']:
                subnet_id = subnet['subnet_id']
                # Find the corresponding instances for this subnet
                subnet_instances = next((si['instances'] for si in subnets_and_instances if si['subnet_id'] == subnet_id), [])
                # Add the instances to the subnet data
                subnet['instances'] = subnet_instances
        return vpcs_and_subnets

    def generate_d2_diagram(self, vpc_data):
        # Render the Jinja2 template with the correlated data
        template = self.env.get_template('aws_diagram_template.d2')
        return template.render(vpcs=vpc_data)

    def save_diagram_to_file(self, diagram_data, filename="aws_diagram.d2"):
        # Write the generated D2 diagram to a file
        with open(filename, 'w') as f:
            f.write(diagram_data)

    def create_aws_diagram(self):
        # Step 1: Query VPCs and subnets
        vpcs_and_subnets = self.query_vpcs_and_subnets()
        
        # Step 2: Query subnets and instances
        subnets_and_instances = self.query_subnets_and_instances()

        # Step 3: Correlate subnets with their instances
        correlated_data = self.correlate_data(vpcs_and_subnets, subnets_and_instances)
        
        # Step 4: Generate D2 diagram using the template and correlated data
        d2_diagram = self.generate_d2_diagram(correlated_data)
        
        # Step 5: Save the generated diagram to a file
        self.save_diagram_to_file(d2_diagram)

        print("D2 diagram generated and saved as aws_diagram.d2")


if __name__ == "__main__":
    # Initialize the AWS diagram generator and create the diagram
    diagram_generator = AWSDiagramGenerator()
    diagram_generator.create_aws_diagram()
