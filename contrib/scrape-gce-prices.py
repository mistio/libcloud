import json
from requests import request

def get_all_skus(key):
    # a valid google cloud account API key should be provided
    # https://cloud.google.com/docs/authentication/api-keys
    URL = "https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?key={}"
    URL = URL.format(key)
    url = URL
    data = []
    has_next_page = True
    while has_next_page:
        try:
            response = request(method="GET", url=url)
            response.raise_for_status()
        except Exception as exc:
            raise 
        data.extend(response.json().get('skus', {}))
        next_page = response.json().get('nextPageToken')
        if next_page:
            url = URL+"&pageToken={}".format(next_page)
        else:
            has_next_page = False
    
    return data

def price_from_units_nano(units, nano):
    nano = str(nano)
    nano = "0"*(9-len(nano)) + nano
    units = str(units)
    price = units + "." + nano
    return float(price)

if __name__ == "__main__":
    key = "AIzaSyDX2eRlE8e2EIpRb4uDNDE2781Fg8f8rcs"
    data = get_all_skus(key)
    n1standard = []
    usage_type_map = {
        "OnDemand": 'on_demand',
        "Preemptible": 'preemptible',
        "Commit1Yr": '1yr_commitment',
        "Commit3Yr": '3yr_commitment'
    }
    # compute -> gce_instances --> instance type --> usage type (On demand, preemptible, Commitment) --> region --> price/hour
    compute = {
        'gce_instances': {
            'N1_predefined': {
                'cpu':{
                    'description': 'N1 Predefined Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'N1 Predefined Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N1_custom': {
                'cpu':{
                    'description': 'Custom Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'Custom Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N1_custom_extended':{
                'cpu': {},
                'ram':{
                    'description': 'Custom Extended Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N2_predefined': {
                'cpu':{
                    'description': 'N2 Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'N2 Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N2_custom': {
                'cpu':{
                    'description': 'N2 Custom Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'N2 Custom Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N2_custom_extended': {
                'cpu': {},
                'ram':{
                    'description': 'N2 Custom Extended Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            # E2 predefined and custom have same prices and no extended
            'E2_predefined': {
                'cpu':{
                    'description': 'E2 Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'E2 Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'E2_custom': {
                'cpu':{
                    'description': 'E2 Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'E2 Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            }, 
            'N2D_prefined': {
                'description': 'N2D AMD',
                'cpu':{
                    'description': 'N2D AMD Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'N2D AMD Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N2D_custom': {
                'cpu':{
                    'description': 'N2D AMD Custom Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'N2D AMD Custom Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'N2D_custom_extended': {
                'cpu': {},
                'ram':{
                    'description': 'N2D AMD Custom Extended Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                }
            },
            # M1 memory optimized, no custom
            'M1_predefined': {
                'cpu':{
                    'description': 'Memory-optimized Instance Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'Memory-optimized Instance Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            },
            'C2_predefined': {
                'cpu':{
                    'description': 'Compute optimized Core',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
                'ram':{
                    'description': 'Compute optimized Ram',
                    'on_demand': {},
                    'preemptible': {},
                    '1yr_commitment': {},
                    '3yr_commitment': {}
                },
            }
        }
    }
    for sku in data:
        # to make sure I get the correct memory optimized
        if 'Premium' in sku['description']:
            continue
        for item in compute['gce_instances'].values():
            for resource in {'cpu', 'ram'}:
                description = item[resource].get('description', "-----")
                if description in sku['description']:
                    location = sku['serviceRegions'][0]
                    usage_type = usage_type_map[sku['category']['usageType']]
                    units = sku['pricingInfo'][0]['pricingExpression'][
                        'tieredRates'][0]['unitPrice']['units']
                    nanos = sku['pricingInfo'][0]['pricingExpression'][
                        'tieredRates'][0]['unitPrice']['nanos']
                    price = price_from_units_nano(units, nanos)
                    item[resource][usage_type][location] = price
    print(compute['gce_instances'])