#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include <Arduino.h>

void wifi_init();
bool wifi_is_connected();
void wifi_reconnect();

void mqtt_init();
bool mqtt_is_connected();
void mqtt_reconnect();
void mqtt_loop();
void mqtt_publish(const char* topic, const char* payload);
void mqtt_subscribe(const char* topic);

// Callback type for incoming MQTT commands
typedef void (*MqttCommandCallback)(const char* topic, const char* payload);
void mqtt_set_command_callback(MqttCommandCallback cb);

// NTP time sync (A-03)
void syncNTP();
uint64_t getUnixMs();

#endif
