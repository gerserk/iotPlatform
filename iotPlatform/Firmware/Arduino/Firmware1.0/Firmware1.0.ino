#include <WiFiNINA.h>
#include <ArduinoJson.h>
#include <ArduinoHttpClient.h>
#include <PubSubClient.h>

int status = WL_IDLE_STATUS;
char ssid[] = "";
char password[] = "";
WiFiSSLClient client; 
WiFiClient mqtt; 

char host[]="";

// HTTP
String tokenUri   = "/dh/auth/rest/token";
String commandUri = "/dh/api/rest/device/ArduinoB/command"; // put your machine here
String contentType = "application/json";
HttpClient clientH = HttpClient(client, host, 443);

// MQTT 
char client_id[]="client"; // client  MQTT 
char device_id[]="ArduinoB"; // machine name, NO UNDERSCORE (_)
char auth_topic[32]="dh/response/authenticate@";
const char* authTopic= strcat(auth_topic, client_id);
char save_topic[32]="dh/response/device/save@";
const char* saveTopic = strcat(save_topic, client_id);
char notif_topic[39]="dh/response/notification/insert@";
const char* notifTopic = strcat(notif_topic, client_id);
int request_id= 1234;
PubSubClient mqttClient(mqtt);

// callback function for MQTT
void Callback(char* topic, byte* payload, unsigned int length){
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
}

// function to compile headers string
String Headers(String JWT) {
  String bearerString = "Bearer " + JWT;
  String header = "Authorization: Bearer " + JWT;
  return header;
}

// Function to keep MQTT alive
void MQTTreconnect() {
  // Loop until we're reconnected
  while (!mqttClient.connected()) {
    // Attempt to connect
    if (mqttClient.connect(client_id)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

String Authentication() { 
  // POST request
  clientH.post(tokenUri, contentType, "{'login':'yourUser', 'password':'yourPass'}");
  String auth = clientH.responseBody();

  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, auth);
  if (error) {
    Serial.print(F("token deserializeJson() failed: "));
    Serial.println(error.f_str());
  }
  else {
    
    const char* token1 = doc["accessToken"];
    //const char* token2 = doc["refreshToken"];
    String JWT = token1;
    //String JWS = token2;  
    return JWT;
  }}


void setup() {
  // connetti wifi
  Serial.begin(9600);
  while (!Serial) continue;
  while (status != WL_CONNECTED) {
    status = WiFi.begin(ssid, password);
    delay(1000);
  }
  
  // Set il server per l'MQTT
  mqttClient.setServer(host,1883);
  mqttClient.setCallback(Callback);

  // Connetti al broker (tutti i print si possono togliere)
  if (mqttClient.connect(client_id) ) {
    Serial.println("mqtt connected"); 
    } 
    else {
    Serial.println("mqtt not connected");
    Serial.print("failed, rc=");
    Serial.println(mqttClient.state()); }

  // creta il loop MQTT
  mqttClient.loop();
  
  delay(500);
  
  String JWT = Authentication(); // funzione da un token; quando scade (controlla se gli altri statuscode =! -2) bisogna richiamarla per averne un altro 
  // autenticazione MQTT, uso il JWT appena ottenuto
  delay(500);
  mqttClient.subscribe(authTopic); 
  delay(500);
  char authPayload[300];
  StaticJsonDocument<256> docAuth;
  docAuth["action"] = "authenticate";
  docAuth["requestId"] = request_id;
  docAuth["token"] = JWT;
  serializeJson(docAuth, authPayload);
  mqttClient.publish("dh/request", authPayload);

  delay(500);
  // Salvo dispositivo
  mqttClient.subscribe(saveTopic);
  char deviceSavePayload [200];
  StaticJsonDocument<96> docSave;
  docSave["action"] = "device/save";
  docSave["deviceId"] = device_id;
  docSave["device"]["name"] = device_id; // puoi dargli un nome diverso dal device id, in ogni caso sulla piattaforma vedrai sempre i device id
  serializeJson(docSave, deviceSavePayload);
  mqttClient.publish("dh/request",deviceSavePayload); 

  // Autorizzo dispositivo a mandare notifiche (dati sensori + stato attuatori)
  mqttClient.subscribe(notifTopic); 

}

void loop() {
  // Questa bisognerebbe metterla "fuori dal loop"
  String JWT = Authentication();
  String header = Headers(JWT);
  int count = 0; 
  while (count < 5){   // loop per non dover fare continuamente l'autenticazione, se chiami troppo spesso inzia a dare errore.
  // Teoricamente una volta che il JWT "scade" ( ha un limite temporale), bisogna rifare l'autenticazione o usare il JWS facendo una nuova chiamata
    count ++;

    // se non son più connesso mi riconnetto con il broker
    if (!mqttClient.connected()) {
      MQTTreconnect();
      }
    
    // Creo e pubblico messaggi notifica
    char notifPayload [200];
    StaticJsonDocument<96> docNotif; // GRANDEZZA DA VEDERE IN BASE A TUTTI I SENSORI https://arduinojson.org/v6/assistant/#/step1, assistant che ti dice quanto fare grande il documento
    docNotif["action"] = "notification/insert";
    docNotif["deviceId"] = device_id;
    JsonObject notification = docNotif.createNestedObject("notification");
    notification["notification"] = "temperaturesensor";
    JsonObject notification_parameters = notification.createNestedObject("parameters");
    notification_parameters["a_T1"] = 25;
    notification_parameters["d_hall1"] = 2; // qui posso aggiungere tutti i parametri (sensori e basta) che voglio
    serializeJson(docNotif, notifPayload);
    // pubblico notifica sensori
    mqttClient.publish("dh/request", notifPayload);

    // STESSA COSA DI PRIMA PER ATTUATORI/Utilities
    char actPayload [250];
    StaticJsonDocument<192> docAct;
    docAct["action"] = "notification/insert";
    docAct["deviceId"] = device_id;
    JsonObject notification2 = docAct.createNestedObject("notification");
    notification["notification"] = "commandReceived";
    JsonObject notification_parameters2 = notification2.createNestedObject("parameters");
    notification_parameters2["LED"] = 1; 
    serializeJson(docAct, actPayload);
    mqttClient.publish("dh/request", actPayload);

    delay(500);
    
    int err = 0;
    clientH.beginRequest();
    err = clientH.get(commandUri); 
    clientH.sendHeader(header);
    clientH.endRequest();
    if (err == 0 ){
    String Command = clientH.responseBody();
    //int comStatusCode = clientH.responseStatusCode();
    //Serial.println(comStatusCode);
    //Serial.println("Command:");
    //Serial.println(Command);
    
    delay(500);

    if (Command != "[]") {
          
      JsonDocument docComm;
      deserializeJson(docComm, Command);

      JsonObject root_0 = docComm[0];
      long root_0_id = root_0["id"]; // ID comando
      
      const char* LEDricevuto = root_0["parameters"]["LED"]; 

      //Serial.println("Valori:");
      Serial.println(LEDricevuto);
      Serial.println(MODEricevuto);
      
      }

    
    }
    delay(1500);
    }
  delay(10000);

}
