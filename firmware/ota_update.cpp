/*
 * AgriMaster Pro — OTA (Over-The-Air) Update Implementation
 * Allows firmware updates over WiFi without physical USB connection.
 */
#include "ota_update.h"
#include "config.h"
#include <Arduino.h>
#include <ArduinoOTA.h>

void otaSetup(const char* hostname, const char* password) {
  ArduinoOTA.setHostname(hostname);
  if (password && strlen(password) > 0) {
    ArduinoOTA.setPassword(password);
  }
  ArduinoOTA.setPort(3232);

  ArduinoOTA.onStart([]() {
    String type = (ArduinoOTA.getCommand() == U_FLASH) ? "firmware" : "filesystem";
    Serial.println("[OTA] Start updating " + type);
  });

  ArduinoOTA.onEnd([]() {
    Serial.println("\n[OTA] Update complete! Rebooting...");
  });

  ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
    Serial.printf("[OTA] Progress: %u%%\r", (progress / (total / 100)));
  });

  ArduinoOTA.onError([](ota_error_t error) {
    Serial.printf("[OTA] Error[%u]: ", error);
    if (error == OTA_AUTH_ERROR) Serial.println("Auth Failed");
    else if (error == OTA_BEGIN_ERROR) Serial.println("Begin Failed");
    else if (error == OTA_CONNECT_ERROR) Serial.println("Connect Failed");
    else if (error == OTA_RECEIVE_ERROR) Serial.println("Receive Failed");
    else if (error == OTA_END_ERROR) Serial.println("End Failed");
  });

  ArduinoOTA.begin();
  Serial.printf("[OTA] Ready (hostname: %s, port: 3232)\n", hostname);
}

void otaHandle() {
  ArduinoOTA.handle();
}
