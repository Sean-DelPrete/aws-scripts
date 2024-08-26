import boto3
import pandas as pd
import json
from tabulate import tabulate

def get_instance_types(service_code, region, db_engine=None):
    """Fetch instance types and their specifications from AWS Pricing API."""
    client = boto3.client('pricing', region_name='us-east-1')  # Pricing is only available in us-east-1

    filters = [
        {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
        
    ]
    if db_engine:
        filters.append({'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': db_engine})

    instance_types = {}
    paginator = client.get_paginator('get_products')
    for page in paginator.paginate(ServiceCode=service_code, Filters=filters):
        for price_list in page['PriceList']:
            product = json.loads(price_list)['product']
            attributes = product['attributes']
            instance_type = attributes.get('instanceType')
            if instance_type and ('5' in instance_type or '6' in instance_type):
                memory_str = attributes.get('memory', '0').split()[0]
                try:
                    memory = float(memory_str)
                except ValueError:
                    memory = 0  # Handle non-numeric memory values
                instance_types[instance_type] = {
                    'vCPU': int(attributes.get('vcpu', 0)),
                    'memory': memory,
                }

    print(f"Fetched {len(instance_types)} instance types for {service_code}")
    return instance_types

def get_rds_pricing(region, instance_type, db_engine, deployment_option, storage_gb):
    """Fetch RDS pricing information using Boto3."""
    client = boto3.client('pricing', region_name='us-east-1')  # Pricing is only available in us-east-1

    response = client.get_products(
        ServiceCode='AmazonRDS',
        Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'databaseEngine', 'Value': db_engine},
            {'Type': 'TERM_MATCH', 'Field': 'deploymentOption', 'Value': deployment_option},
           # {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used' },
           # {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA' },
           # {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'shared' }
        ]
    )

    price_list = response['PriceList']
    if not price_list:
        return None

    price_details = json.loads(price_list[0])
    on_demand = price_details['terms']['OnDemand']
    price_dimensions = next(iter(on_demand.values()))['priceDimensions']
    price_per_unit = next(iter(price_dimensions.values()))['pricePerUnit']['USD']
    
    # Convert hourly price to monthly price (assuming 730 hours per month)
    price_per_month = float(price_per_unit) * 730

    # Adding storage cost (assuming gp2 SSD)
    storage_price = 0.115  # USD per GB-month for gp2 SSD
    storage_total = storage_price * storage_gb
    total_price = price_per_month + storage_total
    
    print(f"Price for ID: per unit {price_per_unit} for instance {instance_type} Engine: {db_engine} Monthly: {price_per_month} with storage {storage_gb} GB {storage_total}: Total Price: {total_price}")
    return total_price

def get_ec2_pricing(region, instance_type, storage_gb):
    """Fetch EC2 pricing information using Boto3."""
    client = boto3.client('pricing', region_name='us-east-1')  # Pricing is only available in us-east-1

    response = client.get_products(
        ServiceCode='AmazonEC2',
        Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'termType', 'Value': 'OnDemand' },
        ]
    )

    price_list = response['PriceList']
    if not price_list:
        return None

    price_details = json.loads(price_list[0])
    on_demand = price_details['terms']['OnDemand']
    price_dimensions = next(iter(on_demand.values()))['priceDimensions']
    price_per_unit = next(iter(price_dimensions.values()))['pricePerUnit']['USD']
    
    # Convert hourly price to monthly price (assuming 730 hours per month)
    price_per_month = float(price_per_unit) * 730

    # Adding storage cost (assuming gp2 SSD)  
    storage_price = 0.115  # USD per GB-month for gp2 SSD
    storage_total = storage_price * storage_gb
    total_price = price_per_month + storage_total
    
    print(f"Price per unti {price_per_unit} for instance {instance_type} Monthly: {price_per_month} with storage {storage_gb} GB {storage_total}: Total Price: {total_price}")

    return total_price

def match_instance(instance_types, cpu, memory, get_pricing_func, region, db_engine=None, deployment_option=None, storage_gb=0):
    """Match the provided CPU and memory to the closest instance type that has pricing."""
    matched_instance = None
    for instance, specs in sorted(instance_types.items(), key=lambda x: (x[1]['vCPU'], x[1]['memory'])):
        if specs['vCPU'] >= cpu and specs['memory'] >= memory:
            # Check if this instance type has pricing
            if db_engine and deployment_option:
                price = get_pricing_func(region, instance, db_engine, deployment_option, storage_gb)
            else:
                price = get_pricing_func(region, instance, storage_gb)

            if price is not None:
                matched_instance = instance
                break

    if matched_instance:
        print(f"Matched instance: {matched_instance} with specs vCPU: {cpu}, Memory: {memory}")
    else:
        print(f"No match found for specs vCPU: {cpu}, Memory: {memory}")
    return matched_instance

def fetch_prices(df, instance_types_rds, instance_types_ec2):
    """Fetch prices for filtered data."""
    region = 'US East (N. Virginia)'  # Define the region you want to query
    db_engines = ['SQL Server']
    deployment_options = {
        'Non-Prod': 'Single-AZ',
        'Prod': 'Multi-AZ'
    }

    prices = []

    for index, row in df.iterrows():
        env = row['Environment']
        deployment_option = deployment_options['Prod' if env == 'PROD' else 'Non-Prod']
        
        # Match instance type based on provided specifications
        cpu = row['NumberOfCores']
        memory = row['TotalMemoryInGB']
        storage_gb = row['StorageGB']
        ID = row['ID']

        instance_type_ec2 = match_instance(instance_types_ec2, cpu, memory, get_ec2_pricing, region, storage_gb=storage_gb)
        if instance_type_ec2:
            ec2_price = get_ec2_pricing(region, instance_type_ec2, storage_gb)
            if ec2_price is not None:
                prices.append({
                    'ID': ID,
                    'Environment': env,
                    'InstanceType': instance_type_ec2,
                    'Service': 'EC2',
                    'DeploymentOption': deployment_option,
                    'PricePerMonth': ec2_price,
                    'NumberOfCores': cpu,
                    'TotalMemoryInGB': memory,
                    'StorageGB': storage_gb
                })
            else:
                print(f"No pricing found for EC2 instance type: {instance_type_ec2}")

        for db_engine in db_engines:
            instance_type_rds = match_instance(instance_types_rds, cpu, memory, get_rds_pricing, region, db_engine, deployment_option, storage_gb)
            if instance_type_rds:
                price = get_rds_pricing(region, instance_type_rds, db_engine, deployment_option, storage_gb)
                if price is not None:
                    prices.append({
                        'ID': ID,
                        'Environment': env,
                        'InstanceType': instance_type_rds,
                        'Service': f'RDS ({db_engine})',
                        'DeploymentOption': deployment_option,
                        'PricePerMonth': price,
                        'NumberOfCores': cpu,
                        'TotalMemoryInGB': memory,
                        'StorageGB': storage_gb
                    })
                else:
                    print(f"No pricing found for RDS instance type: {instance_type_rds}, DB engine: {db_engine}, deployment option: {deployment_option}")
            else:
                print(f"No match found for RDS instance type with specs vCPU: {cpu}, Memory: {memory}, DB engine: {db_engine}")

    return prices

if __name__ == '__main__':
    file_path = 'ffa_server_list.xlsx'
    df = pd.read_excel(file_path, sheet_name='Sheet1')

    # Fetch instance types and their specifications
    region = 'US East (N. Virginia)'
    instance_types_rds = get_instance_types('AmazonRDS', region)
    instance_types_ec2 = get_instance_types('AmazonEC2', region)

    non_prod_df = df[df['Environment'].str.contains('PREPROD|DEV|TEST', case=False)]
    prod_df = df[df['Environment'].str.match('^PROD$', case=False)]

    non_prod_prices = fetch_prices(non_prod_df, instance_types_rds, instance_types_ec2)
    prod_prices = fetch_prices(prod_df, instance_types_rds, instance_types_ec2)

    all_prices = non_prod_prices + prod_prices

    # Pretty print the results
    print("\nPrices per month:")
    print(tabulate(all_prices, headers="keys", tablefmt="grid"))

    # Write results to a CSV file
    output_df = pd.DataFrame(all_prices)
    output_df.to_csv('pricing_output.csv', index=False)
    print("\nPricing details have been saved to pricing_output.csv")