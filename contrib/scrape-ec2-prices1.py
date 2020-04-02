import json
import os
BASE_URL = ""

# temporary
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
PRICING_FILE_PATH = os.path.join(BASE_PATH, './tmp/useast.json')
us_east_file = os.path.abspath(PRICING_FILE_PATH)


def scrape_prices():
    with open(us_east_file) as f:
        content = f.read()
    
    data = json.loads(content)
    #['formatVersion', 'disclaimer', 'offerCode', 'version', 'publicationDate', 'products', 'terms']
    products = data['products']
    all_skus = list(data['products'].keys())
    # ['sku', 'productFamily', 'attributes']<---> product['sku']
    #####################################
    # ['servicecode', 'location', 'locationType', 'instanceType', 'currentGeneration', 'instanceFamily', 
    # 'vcpu', 'physicalProcessor', 'clockSpeed', 'memory', 'storage', 'networkPerformance', 'processorArchitecture', 
    # 'tenancy', 'operatingSystem', 'licenseModel', 'usagetype', 'operation', 'capacitystatus', 'dedicatedEbsThroughput',
    # 'ecu', 'enhancedNetworkingSupported', 'instancesku', 'intelAvxAvailable', 'intelAvx2Available', 
    # 'intelTurboAvailable', 'normalizationSizeFactor', 'preInstalledSw', 'processorFeatures', 'servicename'] 
    #  product['sku']['attributes']
    print(products[all_skus[-100]]['attributes']['instanceType'])
    
    instances = []
    xxx = 0
    for sku in all_skus:
        instance = {'OS':products[sku]['attributes'].get('operatingSystem','None?'),
                    'type':products[sku]['attributes'].get('instanceType', "Nothing?"),
                    'sku':sku,
                    'instancesku': products[sku]['attributes'].get('instancesku', 'Nope?!')}
        instances.append(instance)
        if products[sku]['productFamily'] != "Compute Instance":
            xxx+=1
    prices = data['terms']['OnDemand']
    print(xxx, len(all_skus))
    check = 'a1.2xlarge'
    checks = []
    for instance in instances:
        if check == instance['type']:
            ddd = prices[instance['sku']]
            dd = list(ddd.values())[0]
            instance['offerTermCode'] = dd['offerTermCode']
            instance['priceDimensions'] = dd['priceDimensions']
            checks.append(instance)
    '''
    for ccc in checks:
        print(ccc)
        print("\n-----------\n")
    print(len(checks))
    '''
if __name__=="__main__":
    scrape_prices()