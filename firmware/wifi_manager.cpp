#include "wifi_manager.h"
#include "config.h"
#include <WiFi.h>
#include <PubSubClient.h>
#include <time.h>

static WiFiClient espClient;
static PubSubClient mqttClient(espClient);
static MqttCommandCallback cmdCallback = nullptr;
static unsigned long lastMqttAttempt = 0;

// ═══ Internal MQTT callback ═══
static void mqtt_internal_callback(char* topic, byte* payload, unsigned int length) {
  char msg[512];
  unsigned int len = min(length, (unsigned int)511);
  memcpy(msg, payload, len);
  msg[len] = '\0';

  Serial.printf("[MQTT] Received on %s: %s\n", topic, msg);

  if (cmdCallback) {
    cmdCallback(topic, msg);
  }
}

// ═══ WiFi ═══
void wifi_init() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] Connection failed, will retry...");
  }
}

bool wifi_is_connected() {
  return WiFi.status() == WL_CONNECTED;
}

void wifi_reconnect() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.println("[WIFI] Reconnecting...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASS);
}

// ═══ MQTT ═══
void mqtt_init() {
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqtt_internal_callback);
  mqttClient.setBufferSize(1024);
  Serial.println("[MQTT] Client initialized");
}

bool mqtt_is_connected() {
  return mqttClient.connected();
}

void mqtt_reconnect() {
  if (mqttClient.connected()) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = millis();

  Serial.printf("[MQTT] Connecting to %s:%d...\n", MQTT_BROKER, MQTT_PORT);
  String clientId = String(DEVICE_ID) + "_" + String(random(0xFFFF), HEX);

  if (mqttClient.connect(clientId.c_str())) {
    Serial.println("[MQTT] Connected!");
    mqttClient.subscribe(TOPIC_CMD);
    Serial.printf("[MQTT] Subscribed to %s\n", TOPIC_CMD);

    // Publish online status
    String status = "{\"device_id\":\"" + String(DEVICE_ID) + "\",\"status\":\"online\"}";
    mqttClient.publish(TOPIC_STATUS, status.c_str(), true);
  } else {
    Serial.printf("[MQTT] Failed, rc=%d. Will retry in %dms\n",
                  mqttClient.state(), MQTT_RETRY_MS);
  }
}

void mqtt_loop() {
  if (!mqttClient.connected()) {
    mqtt_reconnect();
  }
  mqttClient.loop();
}

void mqtt_publish(const char* topic, const char* payload) {
  if (!mqttClient.connected()) return;
  bool ok = mqttClient.publish(topic, payload);
  if (!ok) {
    Serial.printf("[MQTT] Publish failed to %s\n", topic);
  }
}

void mqtt_subscribe(const char* topic) {
  if (mqttClient.connected()) {
    mqttClient.subscribe(topic);
  }
}

void mqtt_set_command_callback(MqttCommandCallback cb) {
  cmdCallback = cb;
}

// ═══ NTP Time Sync (A-03) ═══
void syncNTP() {
  configTime(TIMEZONE_OFFSET_SEC, 0, "pool.ntp.org", "time.nist.gov");
  struct tm timeinfo;
  int retries = 0;
  while (!getLocalTime(&timeinfo) && retries < 20) {
    delay(500);
    retries++;
  }
  if (retries < 20) {
    Serial.println("[NTP] Time synchronized");
    Serial.printf("[NTP] %04d-%02d-%02d %02d:%02d:%02d UTC+3\n",
                  timeinfo.tm_year+1900, timeinfo.tm_mon+1, timeinfo.tm_mday,
                  timeinfo.tm_hour, timeinfo.tm_min, timeinfo.tm_sec);
  } else {
    Serial.println("[NTP] Time sync failed after 20 retries");
  }
}

uint64_t getUnixMs() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (uint64_t)(tv.tv_sec) * 1000ULL + (tv.tv_usec / 1000ULL);
}
