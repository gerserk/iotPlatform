import uvicorn
import json, math
import requests
from fastapi import FastAPI,Request
import influxdb_client, os, time
from influxdb_client import  Point
from influxdb_client.client.write_api import SYNCHRONOUS
from devicehive import Handler
from devicehive_plugin import Plugin
from multiprocessing import Process
from apiMethods import apiMethods


script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
os.chdir(script_dir)

app = FastAPI()

# 2 processes:

def plugin_connect():
    plugin = Plugin(SimpleHandler)
    time.sleep(2)
    tokens=apiMethod.authenticate_user(dh_credentials["user"],dh_credentials["password"])
    JWT=tokens['accessToken']
    endPoints=apiMethod.topic_caller(JWT)
    topic_name=endPoints['topicName']
    url=endPoints['proxyEndpoint']

    authUrl=requests.get(config['endpoints']['auth'])
    authUrl=apiMethod.extractLink(authUrl)

    plugin.connect(url, topic_name, auth_url=authUrl,
                login=dh_credentials["user"], password=dh_credentials["password"])

def app_start():
    uvicorn.run(app, host="0.0.0.0", port=5000)

def findbucket_by_name(client,name):
    info_bucket=client.find_bucket_by_name(name)
    list=info_bucket.to_dict()
    return(list)
   
############# PLUGIN #################

class SimpleHandler(Handler):

    def handle_connect(self):
        pass

    def handle_event(self, event):
        if event.action=="notification/insert":
            self.n=1

    def handle_command_insert(self, command): # will be called after command/insert event is received
        pass # POST /api/rest/device/NAME/command  (sent command to device NAME)

    def handle_command_update(self, command): # will be called after command/update event is received
        pass # updates existing command

    def handle_notification(self, notification): # will be called after notification/insert event is received
        
        if notification.notification != config["dataTypes"]["command"]:
            device_id= notification.device_id
            if self.n==1:  # if the action is to insert a notification
                self.n=0
                parameter=notification.parameters
                for measurment in parameter.keys(): # here i call every type of measure in the dictionary
                    typeOfMeasure=1

                    value=parameter[measurment] # new measuremnent automatically registered
                    self.bucket=f"{device_id}"
                    old=Bclient.find_bucket_by_name(self.bucket) # current bucket
                    if old is None: 
                        t=config['retention_time'] 
                        Bclient.create_bucket(None,self.bucket, org , {"everySeconds": t}, 'Bucket with no retention')

                    if measurment in config["dataTypes"]['tempList']: # converto valori temp
                        operation = config['conversionValues']['tempList']
                        value = eval(operation)
                    if measurment in config["dataTypes"]["hallList"]: # converto valori hall
                        operation = config['conversionValues']['hallList']
                        value = eval(operation)
                    if measurment in config["dataTypes"]["metadata"]: # scarto metadata
                        typeOfMeasure=0
                    
                    if typeOfMeasure==1:
                        point=Point(measures).tag(sens_name,device_id).field(measurment,value)
                        write_api.write(bucket=self.bucket, org=org, record=point)


############# APP ###################
    
# ping per il catalog
@app.get("/ping")
def ping():
    return {"message": "pong"}

# cancella una macchina + tutti i suoi dati
@app.post("/delete_bucket")
async def read_item(request: Request):
    
    body=await request.body()
    body=json.loads(body)
    
    bucket=body['bucket']
    buckets = Bclient.find_buckets()

    check=False    
    list= buckets.buckets
    for i in range(len(list)):
        pagina=list[i]
        nome=pagina._name
        if nome==bucket:
            check=True
    
    if check is False:
        return({'message':'DATA of this machine does not exist'})
    else:
        bucket_data=findbucket_by_name(Bclient,bucket)
        bucket_id=bucket_data['id']
        Bclient.delete_bucket(bucket_id)
        return({'message':'machine DATA delteted successfully!'})

# ritorna tutti i tipi di misure di una speicifca macchina
@app.get("/listMeasures/{bucket}")
def get_measures(bucket: str):

    
    query = f'from(bucket: "{bucket}") |> range(start: -1y) |> group((columns: ["_field"]) |> distinct(column: "_field") |> yield(name: "fieldValues")'
    query = f'''
            import "influxdata/influxdb/schema"
            
            schema.tagValues(bucket: "{bucket}", tag: "_field")
        '''

    result = client.query_api().query(query)
    
    result=result.to_json()
    result=json.loads(result)
    
    if result is None:
        return({'message':'No measurements available for this machine'})
    measures = [item["_value"] for item in result]
    return({'message':measures})

# prende dati ultimi 15 minuti di una specifica misura e manda al client
@app.post("/realTime")
async def realtime(request: Request):
    body=await request.body()
    body=json.loads(body)

    # # {
    # #     "bucket":"aa",
    #     # "measure":f"{m}"
    # # }

    bucket=body['bucket']
    field=body['measure']
    query_api = client.query_api() 

    query = f'from(bucket:"{bucket}")\
    |> range(start: -15m)\
    |> filter(fn:(r) => r._field == "{field}")' 

    result = query_api.query(org=org, query=query)
    print(result.to_json())
    return result.to_json()

# prende dati da tempo/giorno richiesti e manda al client
@app.post("/query")
async def read_item(request: Request):
    
    body=await request.body()
    body=json.loads(body)

    # message:
    # {
    #    "bucket":"aa",
    #    "startDate":f"{startDate}",
    #    "endDate":f"{endDate}",
    #    "startTime":f"{startTime}",
    #    "endTime":f"{endTime}",
    #    "measure":f"{m}",
    # }

    bucket=body['bucket']
    field=body['measure']
    startDate=body['startDate']
    endDate=body['endDate']
    startTime=body['startTime']
    endTime=body['endTime']


    query_api = client.query_api() 

    query = f'from(bucket:"{bucket}")\
    |> range(start: {startDate}T{startTime}+01:00, stop: {endDate}T{endTime}+01:00)\
    |> filter(fn:(r) => r._field == "{field}")' 

    result = query_api.query(org=org, query=query)
    return result.to_json()

if __name__ == "__main__":
    
    time.sleep(55)
    apiMethod=apiMethods()
    
    # si registra al catalog e salva i dati che il catalog gli da come risposta (endpoints) in config.json
    apiMethod.start()

    with open("config.json", "r") as f:
        config = json.load(f)
    # chiavi influx
    influx_user=config["influx_credentials"]["user"] 
    influx_password=config["influx_credentials"]["password"]
    org = config["org"]
    url_influx = requests.get(config['endpoints']['influx'])
    url_influx= apiMethod.extractLink(url_influx)

    # credenziali dh     
    dh_credentials=config["dh_credentials"]

    # BUCKET KEYS
    measures=config["bucket_keys"]["measurement"]
    sens_name=config["bucket_keys"]["sensor_name"]
    device_commands=config["bucket_keys"]["commands"]

    client = influxdb_client.InfluxDBClient(url=url_influx, username=influx_user, password=influx_password,org=org) 
    write_api = client.write_api(write_options=SYNCHRONOUS)
    Bclient = influxdb_client.BucketsApi(client)

    time.sleep(65)

    plugin_process=Process(target=plugin_connect)
    app_process=Process(target=app_start)
    app_process.start()
    plugin_process.start()
