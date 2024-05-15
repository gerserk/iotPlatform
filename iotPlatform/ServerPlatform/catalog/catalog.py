import uvicorn
import json, asyncio, time, os
import httpx
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
os.chdir(script_dir)

app = FastAPI()


def platformStart(): # when devicehive starts first time, cancels dhadmin and add a new master user
    with open("config.json", "r") as f:
        config = json.load(f)
    usernameToDel= config["userToDel"]["login"]
    passToDel= config["userToDel"]["password"]
    payload = json.dumps({"login":usernameToDel,
                          "password":passToDel})
    try:
        checkIfUser=requests.post(config["links"]["token_url"], payload)
        if checkIfUser.status_code < 400:
            tokens=checkIfUser.json()
            JWT=tokens['accessToken']
            token_string='Bearer '+ JWT
            headers = ({"Authorization":token_string})
        
            # Add master user
            body = json.dumps(config["dhMasteruser"])
            addUser=requests.post(config["links"]["user_url"], data=body, headers=headers)
            if addUser.ok:
                return
            else:
                return
        else:
            return # user exists
    except: 
        return

# registra interfacce, ritorno indietro endpoints DH e api richiesta (volendo si potrebbe implementare metodo
# per farne avere piu api endpoints assieme. In questo caso non serve)
@app.post("/register/interface/{serviceName}")
async def register_interface(data: dict, serviceName: str):

    with open("catalog.json", "r") as f:
        catalog = json.load(f)

    with open("config.json", "r") as f:
        config = json.load(f)
        
    service_names = [service.get("name") for service in catalog["Interfaces"]]
    
    if data['name'] not in service_names:
        catalog["Interfaces"].append(data)
        json.dump(catalog, open("catalog.json", 'w'), indent=4)

    dhEndpoints = {'dhUris':{}}
    dhEndpoints['dhUris']=config['endpoints'] # endpoints di DH
    apiEndopints = {'apiUris':{}}

    for service in catalog.get("Myservices"):
        if service.get("name") == serviceName:
            apiEndopints['apiUris']=service['URIs']
    
    dhEndpoints.update(apiEndopints) #mando file contenente uri di dh e del servizio richiesto 
    return json.dumps(dhEndpoints)

# register service. save its endpoints, name and description, retuirn catalog endpoints
# per servizi DH
@app.post("/register/service") 
async def register_service(data: dict):

    with open("catalog.json", "r") as f:
        catalog = json.load(f)

    with open("config.json", "r") as f:
        config = json.load(f)
        
    service_names = [service.get("name") for service in catalog["Myservices"]]
    
    if data['name'] not in service_names:
        catalog["Myservices"].append(data)
        json.dump(catalog, open("catalog.json", 'w'), indent=4)

    names=config['nameList']
    if data['name'] not in names: 
        config['nameList'].append(data['name'])
        json.dump(config, open("config.json", 'w'), indent=4)

    endpoints=config['endpoints']
    return json.dumps(endpoints)

# what services are online
@app.get("/services") 
def service_provider():
    dh_service_list={}
    my_service_list={'Myservices':[]}
    with open("catalog.json", "r") as f:
        catalog = json.load(f)
    for service in catalog['Myservices']:
         if service.get('status') == 'on':
            my_service_list['Myservices'].append(service)
    
    with open("DHcatalog.json", "r") as f:
        DHcatalog = json.load(f)
    for service in DHcatalog['DHservices']:
         if service.get('status') == 'on':
            dh_service_list[service['name']] = service
    my_service_list.update(dh_service_list)
    return json.dumps(my_service_list)

# return list of all online services
@app.get("/list") 
def service_provider():
    with open("config.json", "r") as f:
        config = json.load(f)
    return(config['nameList'])

# DH endpoints. methods to this given at registration
@app.get("/endopints/{sType}/{endpoint}")
def endpointProvider(sType: str, endpoint: str):
    with open("config.json", "r") as f:
        config = json.load(f)
    if sType == config["typeOfSer"]["deviceHive"] or sType == config["typeOfSer"]["database"]:
        links=config['links']
        if endpoint in links:
            return json.dumps({"message": links[endpoint]})
        else:
            return json.dumps({"message": "error"})
    if sType == config["typeOfSer"]["myApi"]:
        with open("catalog.json", "r") as f:
            catalog = json.load(f)
        services=catalog.get('Myservices', [])
        if any(services):
            for service in catalog['Myservices']:
                if service['name']== endpoint:
                    return json.dumps({"message": service['url']})
            return json.dumps({"message": "error"})
        else:
            return json.dumps({"message": "error"})
    else:
        return json.dumps({"message": "error"})


def check_resource_timestamp(): 
    """
    se l'await non va metto offline con questo (timestamps)
    """
    with open("catalog.json", "r") as f:
        catalog = json.load(f)

    current_time = time.time()
    threshold = 300 
    services=catalog.get('Myservices', [])

    if any(services):
        for service in catalog['Myservices']:
            if current_time - service['t'] > threshold:
                service['status']="off"
    json.dump(catalog, open("catalog.json", "w"), indent=4)

    with open("DHcatalog.json", "r") as f:
        DHcatalog = json.load(f)

    for service in DHcatalog['DHservices']:
        if current_time-service['t'] > threshold:
            service['status']="off"

    json.dump(DHcatalog, open("DHcatalog.json", "w"), indent=4)

# periodic pings to services
async def periodical_checks():
    """
    Esegue controlli periodici sul catalogo.
    Effettua il controllo del timestamp delle risorse e invia ping ai servizi.
    """
    await asyncio.sleep(70) 
    platformStart() 
    
    while True:
        DHcatalog = json.load(open("DHcatalog.json","r"))
        
        await asyncio.sleep(60)  # Attende 60 secondi tra un controllo e l'altro
        check_resource_timestamp()
        async with httpx.AsyncClient() as client:
            for service in DHcatalog['DHservices']:
                response = await client.get(service['url'])
                if response.status_code < 400:
                    service['status']="on"
                    res=response.json()
                    service['t']=convert_to_unix_timestamp(res['serverTimestamp'])
                else:
                    service['status']="off"
            json.dump(DHcatalog, open("DHcatalog.json", 'w'), indent=4)
            
            catalog = json.load(open("catalog.json","r"))
            for service in catalog['Myservices']:
                try:
                    response = await client.get((service['url'] + "ping"))
                    if response.status_code < 400:
                        service['status']="on"
                        service['t']=time.time()
                    else:
                        service['status']='off'
                except:
                    service['status']='off'
            json.dump(catalog, open("catalog.json", 'w'), indent=4)

@app.on_event("startup")
async def startup_event():
    """
    starts periodic checks
    """
    asyncio.create_task(periodical_checks())

def convert_to_unix_timestamp(timestamp_str):
    """
    Convert a timestamp string in the format '2023-08-03T14:07:41.002' to a Unix timestamp.
    """
    # Convert the timestamp string to a datetime object
    dt_object = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%S.%f")

    # Convert the datetime object to a Unix timestamp (seconds since the epoch)
    unix_timestamp = dt_object.timestamp()
    return unix_timestamp

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)