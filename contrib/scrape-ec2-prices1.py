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
    print(type(data))

if __name__=="__main__":
    scrape_prices()