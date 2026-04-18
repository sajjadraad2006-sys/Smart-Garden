/*
 * AgriMaster Pro — Main ESP32 Firmware
 * Reads all sensors, publishes to MQTT, receives actuator commands.
 * Non-blocking loop using millis().
 */

#include "config.h"
#include "sensors.h"
#include "wifi_manager.h"
#include "ota_update.h"
#include <ArduinoJson.h>

// ═══ Actuator State ═══
struct ActuatorState {
  bool pump_main;
  bool zone1;
  bool zone2;
  bool misting;
  uint8_t fan_speed;    // 0-255
  uint8_t light_pwm;    // 0-255
  bool fertilizer;
  bool ph_down;
  bool ph_up;
  bool buzzer;
};

static ActuatorState actuators = {false,false,false,false,0,0,false,false,false,false};

// ═══ Timed auto-off tracking ═══
struct TimedAction {
  bool active;
  unsigned long off_at;
  uint8_t pin;
};
#define MAX_TIMED 10
static TimedAction timedActions[MAX_TIMED];

// ═══ Timing ═══
static unsigned long lastSensorRead = 0;
static unsigned long lastPublish = 0;
static unsigned long lastMqttConnected = 0;
static SensorReadings latestReadings;

// ═══ Sensor Buffers ═══
extern SensorBuffer buffers[10];

// ═══ Actuator pin helper ═══
void set_relay(uint8_t pin, bool on) {
  digitalWrite(pin, on ? LOW : HIGH);  // Active LOW relays
}

void init_actuator_pins() {
  uint8_t relayPins[] = {PIN_PUMP_MAIN, PIN_ZONE1, PIN_ZONE2, PIN_MISTING,
                         PIN_FERTILIZER, PIN_PH_DOWN, PIN_PH_UP, PIN_BUZZER};
  for (auto pin : relayPins) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);  // OFF (active LOW)
  }
  // PWM channels
  ledcSetup(FAN_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_FAN, FAN_CHANNEL);
  ledcSetup(LIGHT_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_GROW_LIGHT, LIGHT_CHANNEL);
  ledcSetup(LED_R_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_LED_R, LED_R_CHANNEL);
  ledcSetup(LED_G_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_LED_G, LED_G_CHANNEL);
  ledcSetup(LED_B_CHANNEL, PWM_FREQ, PWM_RESOLUTION);
  ledcAttachPin(PIN_LED_B, LED_B_CHANNEL);
}

void set_status_led(uint8_t r, uint8_t g, uint8_t b) {
  ledcWrite(LED_R_CHANNEL, r);
  ledcWrite(LED_G_CHANNEL, g);
  ledcWrite(LED_B_CHANNEL, b);
}

// ═══ Map actuator target string → pin ═══
uint8_t target_to_pin(const char* target) {
  if (strcmp(target, "pump_main") == 0) return PIN_PUMP_MAIN;
  if (strcmp(target, "zone1") == 0) return PIN_ZONE1;
  if (strcmp(target, "zone2") == 0) return PIN_ZONE2;
  if (strcmp(target, "misting") == 0) return PIN_MISTING;
  if (strcmp(target, "fertilizer") == 0) return PIN_FERTILIZER;
  if (strcmp(target, "ph_down") == 0) return PIN_PH_DOWN;
  if (strcmp(target, "ph_up") == 0) return PIN_PH_UP;
  if (strcmp(target, "buzzer") == 0) return PIN_BUZZER;
  return 0xFF;
}

void update_actuator_state(const char* target, bool val) {
  if (strcmp(target, "pump_main") == 0) actuators.pump_main = val;
  else if (strcmp(target, "zone1") == 0) actuators.zone1 = val;
  else if (strcmp(target, "zone2") == 0) actuators.zone2 = val;
  else if (strcmp(target, "misting") == 0) actuators.misting = val;
  else if (strcmp(target, "fertilizer") == 0) actuators.fertilizer = val;
  else if (strcmp(target, "ph_down") == 0) actuators.ph_down = val;
  else if (strcmp(target, "ph_up") == 0) actuators.ph_up = val;
  else if (strcmp(target, "buzzer") == 0) actuators.buzzer = val;
}

// ═══ Schedule auto-off ═══
void schedule_off(uint8_t pin, unsigned long duration_ms, const char* target) {
  for (int i = 0; i < MAX_TIMED; i++) {
    if (!timedActions[i].active) {
      timedActions[i].active = true;
      timedActions[i].pin = pin;
      timedActions[i].off_at = millis() + duration_ms;
      Serial.printf("[ACTUATOR] Scheduled auto-off for pin %d in %lu ms\n", pin, duration_ms);
      return;
    }
  }
  Serial.println("[ACTUATOR] No free timed action slots!");
}

// ═══ MQTT Command Handler ═══
void handle_command(const char* topic, const char* payload) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, payload);
  if (err) {
    Serial.printf("[CMD] JSON parse error: %s\n", err.c_str());
    return;
  }

  const char* action = doc["action"];
  const char* target = doc["target"];

  if (!action || !target) {
    Serial.println("[CMD] Missing action or target");
    return;
  }

  if (strcmp(action, "SET_RELAY") == 0) {
    bool value = doc["value"] | false;
    uint8_t pin = target_to_pin(target);
    if (pin == 0xFF) { Serial.printf("[CMD] Unknown target: %s\n", target); return; }

    set_relay(pin, value);
    update_actuator_state(target, value);
    Serial.printf("[CMD] %s → %s\n", target, value ? "ON" : "OFF");

    int duration = doc["duration_sec"] | 0;
    if (duration > 0 && value) {
      schedule_off(pin, duration * 1000UL, target);
    }
  }
  else if (strcmp(action, "SET_PWM") == 0) {
    int value = doc["value"] | 0;
    if (strcmp(target, "fan") == 0) {
      actuators.fan_speed = constrain(value, 0, 255);
      ledcWrite(FAN_CHANNEL, actuators.fan_speed);
    } else if (strcmp(target, "grow_light") == 0) {
      actuators.light_pwm = constrain(value, 0, 255);
      ledcWrite(LIGHT_CHANNEL, actuators.light_pwm);
    }
    Serial.printf("[CMD] PWM %s → %d\n", target, value);
  }

  // Publish confirmation
  StaticJsonDocument<256> conf;
  conf["device_id"] = DEVICE_ID;
  conf["action"] = action;
  conf["target"] = target;
  conf["status"] = "executed";
  conf["timestamp"] = (double)getUnixMs();  // A-03: NTP timestamp
  char confBuf[256];
  serializeJson(conf, confBuf);
  mqtt_publish(TOPIC_STATUS, confBuf);
}

// ═══ Build & publish sensor JSON ═══
void publish_sensor_data() {
  StaticJsonDocument<768> doc;
  doc["device_id"] = DEVICE_ID;
  doc["timestamp"] = (double)getUnixMs();  // A-03: proper NTP timestamp

  JsonObject sensors = doc.createNestedObject("sensors");
  sensors["temperature"] = round(latestReadings.temperature * 10) / 10.0;
  sensors["humidity"] = round(latestReadings.humidity * 10) / 10.0;
  sensors["soil_moisture"] = round(latestReadings.soil_moisture * 10) / 10.0;
  sensors["soil_temp"] = round(latestReadings.soil_temp * 10) / 10.0;
  sensors["ph"] = round(latestReadings.ph * 100) / 100.0;
  sensors["light_lux"] = round(latestReadings.light_lux);
  sensors["co2_ppm"] = round(latestReadings.co2_ppm);
  sensors["wind_kmh"] = round(latestReadings.wind_kmh * 10) / 10.0;
  sensors["rainfall_mm"] = round(latestReadings.rainfall_mm * 10) / 10.0;
  sensors["power_w"] = round(latestReadings.power_w * 10) / 10.0;

  JsonObject acts = doc.createNestedObject("actuators");
  acts["pump_main"] = actuators.pump_main;
  acts["zone1"] = actuators.zone1;
  acts["zone2"] = actuators.zone2;
  acts["misting"] = actuators.misting;
  acts["fan_speed"] = actuators.fan_speed;
  acts["light_pwm"] = actuators.light_pwm;
  acts["fertilizer"] = actuators.fertilizer;
  acts["ph_down"] = actuators.ph_down;
  acts["ph_up"] = actuators.ph_up;

  char buffer[768];
  serializeJson(doc, buffer);
  mqtt_publish(TOPIC_SENSORS, buffer);
}

// ═══ SETUP ═══
void setup() {
  Serial.begin(115200);
  Serial.println("\n═══ AgriMaster Pro v1.0 ═══");

  memset(timedActions, 0, sizeof(timedActions));

  init_actuator_pins();
  sensors_init();

  wifi_init();
  mqtt_init();
  mqtt_set_command_callback(handle_command);

  if (wifi_is_connected()) {
    syncNTP();  // A-03: Sync time via NTP after WiFi connects
    ota_init();
  }

  set_status_led(0, 64, 0);  // Green = ready
  Serial.println("[MAIN] Setup complete");
}

// ═══ LOOP ═══
void loop() {
  unsigned long now = millis();

  // OTA handling
  if (wifi_is_connected()) {
    ota_handle();
  }

  // MQTT keep-alive
  mqtt_loop();
  if (mqtt_is_connected()) {
    lastMqttConnected = now;
  }

  // ─── Read sensors (non-blocking) ───
  if (now - lastSensorRead >= SENSOR_READ_MS) {
    lastSensorRead = now;
    latestReadings = sensors_read_all();

    // Push to circular buffers for outlier detection
    float vals[] = {
      latestReadings.temperature, latestReadings.humidity,
      latestReadings.soil_moisture, latestReadings.soil_temp,
      latestReadings.ph, latestReadings.light_lux,
      latestReadings.co2_ppm, latestReadings.wind_kmh,
      latestReadings.rainfall_mm, latestReadings.power_w
    };
    for (int i = 0; i < 10; i++) {
      if (latestReadings.valid[i]) {
        sensors_push_buffer(&buffers[i], vals[i]);
      }
    }
  }

  // ─── Publish to MQTT ───
  if (now - lastPublish >= PUBLISH_MS) {
    lastPublish = now;
    if (mqtt_is_connected()) {
      publish_sensor_data();
    }
  }

  // ─── Process timed auto-off ───
  for (int i = 0; i < MAX_TIMED; i++) {
    if (timedActions[i].active && now >= timedActions[i].off_at) {
      digitalWrite(timedActions[i].pin, HIGH);  // OFF
      Serial.printf("[ACTUATOR] Auto-off pin %d\n", timedActions[i].pin);
      timedActions[i].active = false;
    }
  }

  // ─── Watchdog: reconnect WiFi if MQTT lost too long ───
  if (!mqtt_is_connected() && (now - lastMqttConnected > WATCHDOG_TIMEOUT_MS)) {
    Serial.println("[WATCHDOG] MQTT lost >60s, reconnecting WiFi...");
    set_status_led(64, 0, 0);  // Red = error
    wifi_reconnect();
    lastMqttConnected = now; // Reset to avoid rapid retries
  }

  // Short yield to prevent WDT reset
  yield();
}
