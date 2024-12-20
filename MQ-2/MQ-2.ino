#include <MQUnifiedsensor.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <NTPClient.h>
#include <WiFiUdp.h>

#define         Board                   ("ESP-32")
#define         Pin                     (34)
#define         Type                    ("MQ-2")
#define         Voltage_Resolution      (3.3)
#define         ADC_Bit_Resolution      (12)
#define         RatioMQ2CleanAir        (9.83) //RS / R0 = 9.83 ppm
// #define WIFI_SSID "DIGI_49f2c8"
#define WIFI_SSID "s3studio"
// #define WIFI_PASSWORD "a7eeb60d"
#define WIFI_PASSWORD "s3studio"
#define MQTT_BROKER "broker.hivemq.com"
#define MQTT_PORT 1883
#define MQTT_TOPIC "sensor/mq2"

MQUnifiedsensor MQ2(Board, Voltage_Resolution, ADC_Bit_Resolution, Pin, Type);

// WiFi client
WiFiClient espClient;

// MQTT client
PubSubClient client(espClient);

// NTP Client
WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "pool.ntp.org", 0, 60000); // Sync every minute

void connectToWiFi() {
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
}

void reconnectMQTT() {
  // Loop until connected to the MQTT broker
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    if (client.connect("ESP3r3r23id2_dsaM_Q_2__4412")) {  // Client ID, user, pass
      Serial.println("connected!");
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(9600);

  connectToWiFi();

  // Set clock
  // Start NTP client
  timeClient.begin();
  while (!timeClient.update()) {
    timeClient.forceUpdate();
  }

  // Ping MQTT broker  
  Serial.println("Pinging MQTT_BROKER");
  IPAddress brokerIP;
  if (WiFi.hostByName(MQTT_BROKER, brokerIP)) {
    Serial.println("Broker IP resolved");
    Serial.print("IP: ");
    Serial.println(brokerIP);
  } else {
    Serial.println("Broker hostname resolution failed");
  }

  // Set MQTT server address
  client.setServer(MQTT_BROKER, MQTT_PORT);

  //Set math model to calculate the PPM concentration and the value of constants
  MQ2.setRegressionMethod(1); //_PPM =  a*ratio^b
  MQ2.setA(3616.1); MQ2.setB(-2.675);

  MQ2.init(); 
 
  Serial.print("Calibrating please wait.");
  float calcR0 = 0;
  for(int i = 1; i<=10; i ++)
  {
    MQ2.update(); // Update data, the arduino will read the voltage from the analog pin
    calcR0 += MQ2.calibrate(RatioMQ2CleanAir);
    Serial.print(".");
  }
  MQ2.setR0(calcR0/10);
  Serial.println("  done!.");
  
  if(isinf(calcR0)) {
    Serial.println("Warning: Conection issue, R0 is infinite (Open circuit detected) please check your wiring and supply");
    while(1);
  }
  if(calcR0 == 0){
    Serial.println("Warning: Conection issue found, R0 is zero (Analog pin shorts to ground) please check your wiring and supply");
    while(1);
   }

  MQ2.serialDebug(true);
}

void loop() {
  if (!client.connected()) {
    reconnectMQTT();
  }
  client.loop();

  // Read sensor data
  MQ2.update();
  float ppm = MQ2.readSensor();
  MQ2.serialDebug();

  // Get current timestamp from NTP
  timeClient.update();
  time_t rawTime = timeClient.getEpochTime();
  struct tm* timeInfo = localtime(&rawTime);

  // Format timestamp into ISO 8601
  char timestamp[25];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%S", timeInfo);

  // Create payload
  String payload = "{\"timestamp\":\"" + String(timestamp) + "\",\"value\":" + String(ppm, 2) + "}";

  // Publish data to MQTT
  Serial.print("Publishing to MQTT: ");
  Serial.println(payload);
  client.publish(MQTT_TOPIC, payload.c_str());
  
  delay(5000);
}
