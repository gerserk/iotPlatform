import requests
import json, os, math, time
from fastapi import FastAPI,Request, HTTPException


class apiMethods():
    def __init__(self):
        with open("config.json", "r") as f:
            config = json.load(f)
        self.config=config
    
    def extractLink(self,response):
        response=json.loads(response.json())
        return response['message']

    def authenticate_user(self,login,password): #vanno passati login e pass

        payload=json.dumps({
        "login": login,
        "password": password })
        tokenUrl= requests.get(self.config['endpoints']['token'])
        tokenUrl=self.extractLink(tokenUrl)
        
        response=requests.post(tokenUrl,payload)
            # {
            #   "accessToken": "string",
            #   "refreshToken": "string"
            # }
        if response.ok:
            return(response.json())
        else:
            raise HTTPException(status_code=response.status_code)

    def deleteOldPlugin(self,headers): # funzione per eliminare vecchio plugin (controlla se ha lo stesso nome)
        pluginListUrl=requests.get(self.config['endpoints']['pluginList'])
        pluginListUrl=self.extractLink(pluginListUrl)

        pluginList=requests.get(pluginListUrl,headers=headers)
        if pluginList.ok:
            pluginList=pluginList.json()
            if pluginList is None:
                return
            else:
                for plugin in pluginList:
                    if plugin['name']==self.config['plugin']['name']:
                        topicName=plugin['topicName']
                        pluginDelUrl=requests.get(self.config['endpoints']['pluginDel'])
                        pluginDelUrl=self.extractLink(pluginDelUrl)
                        delUrl=pluginDelUrl + topicName
                        response=requests.delete(delUrl,headers=headers)
                        if response.ok:
                            return
                        else:
                            raise HTTPException(status_code=response.status_code)

    def topic_caller(self,JWT):
        payload=json.dumps({
            "name": self.config['plugin']['name'],
            "description": self.config['plugin']['description']
            })
        token_string='Bearer '+ JWT
        headers = ({"Authorization":token_string})

        topicUrl=requests.get(self.config['endpoints']['topic'])
        topicUrl=self.extractLink(topicUrl)

        time.sleep(1)
        self.deleteOldPlugin(headers)

        response=requests.post(topicUrl,payload,headers=headers)
        if response.ok:
            return(response.json())
        # response.json() = {   
            # "topicName": "string",
            # "proxyEndpoint":"string"
            # }
        else:
            raise HTTPException(status_code=response.status_code)

    def refresh_token(self,JWS):

        refreshUrl=requests.get(self.config['endpoints']['refresh'])
        refreshUrl=self.extractLink(refreshUrl)
        
        payload=json.dumps({
            "refreshToken": JWS })
        
        response=requests.post(refreshUrl,payload)
        if response.ok:
            return(response.json())
        #  response.json() = {
            # "accessToken": "string"
            #   }
        else:
            raise HTTPException(status_code=response.status_code)

    def start(self): # registers with catalog, sends its endpoint and takes the dh ones
        registration=self.config['registration']
        registration['t']=time.time()
        registration=json.dumps(registration)
        response = requests.post(self.config['links']['registerCatalog'], registration)
        if response.ok:
            endpoints=json.loads(response.json())
            self.config['endpoints'] = endpoints
            json.dump(self.config, open("config.json", 'w'), indent=4)
        else:
            raise HTTPException(status_code=response.status_code)
    