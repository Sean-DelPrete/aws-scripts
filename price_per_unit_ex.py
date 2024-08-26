import boto3
import json

def get_effective_ec2_price(instance_type, region):
    pricing_client = boto3.client('pricing', region_name='us-east-1')

    try:
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=[
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'termType', 'Value': 'OnDemand'},
            {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Compute Instance'},
            ]
        )

        price_list = response['PriceList']
        for price_item in price_list:
            price_data = json.loads(price_item)
            print([price_list])
            # Example: Find the On-Demand pricing
            if 'OnDemand' in price_data['terms']:
                on_demand_offer = price_data['terms']['OnDemand'][next(iter(price_data['terms']['OnDemand']))]
                price_dimensions = on_demand_offer['priceDimensions']
                
                # Example: Iterate through price dimensions to find the effective price
                for dimension_key, dimension_value in price_dimensions.items():
                    price_per_unit = dimension_value['pricePerUnit']['USD']
                    unit = dimension_value['unit']
                    
                    # You might have additional logic here to determine the most relevant price
                    
                    return price_per_unit, unit

        # If no suitable price found
        return None, None

    except Exception as e:
        print(f"Error fetching data from AWS Price List API: {e}")
        return None, None

# Example usage
instance_type = 't3.large'
region = 'us-east-1'

price, unit = get_effective_ec2_price(instance_type, region)
if price is not None:
    print(f"The effective price per {unit} for instance type {instance_type} in region {region} is ${price}")
else:
    print(f"Could not retrieve effective pricing information for instance type {instance_type} in region {region}")
