import boto3
import json

def get_rds_instance_types():
    # Create a session using your AWS credentials
    session = boto3.Session()

    # Create a pricing client
    pricing_client = session.client('pricing', region_name='us-east-1')

    # Fetch RDS instance types details
    response = pricing_client.get_products(
        ServiceCode='AmazonRDS',
        Filters=[
            {
                'Type': 'TERM_MATCH',
                'Field': 'productFamily',
                'Value': 'Database Instance'
            }
        ],
        MaxResults=100
    )

    instance_types = []

    for price_item in response['PriceList']:
        product = json.loads(price_item)['product']
        attributes = product['attributes']
        instance_type = attributes.get('instanceType')
        vcpu = attributes.get('vcpu')
        memory = attributes.get('memory')
        engine = attributes.get('databaseEngine')

        if instance_type and vcpu and memory and engine:
            instance_types.append({
                'InstanceType': instance_type,
                'vCPU': vcpu,
                'Memory': memory,
                'Engine': engine
            })

    return instance_types

def main():
    instance_types = get_rds_instance_types()

    for instance in instance_types:
        print(f"Instance Type: {instance['InstanceType']}")
        print(f"vCPU: {instance['vCPU']}")
        print(f"Memory: {instance['Memory']}")
        print(f"Supported Engine: {instance['Engine']}")
        print('---')

if __name__ == "__main__":
    main()
