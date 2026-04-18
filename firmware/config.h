#ifndef CONFIG_H
#define CONFIG_H

// ═══ WiFi ═══
#define WIFI_SSID       "YOUR_SSID"
#define WIFI_PASS       "YOUR_PASSWORD"

// ═══ MQTT ═══
#define MQTT_BROKER     "192.168.1.100"
#define MQTT_PORT       1883
#define DEVICE_ID       "agrimaster_01"

// MQTT Topics (publish)
#define TOPIC_SENSORS   "agrimaster/sensors"
#define TOPIC_STATUS    "agrimaster/status"
// MQTT Topics (subscribe)
#define TOPIC_CMD       "agrimaster/commands"

// ═══ Sensor Pins ═══
#define PIN_DHT22       36   // Moved from GPIO 4 (now used by LED Blue)
#define PIN_SOIL_MOIST  34   // ADC
#define PIN_PH          35   // ADC
#define PIN_BH1750_SDA  21
#define PIN_BH1750_SCL  22
#define PIN_MHZ19_TX    17   // ESP32 TX → sensor RX (send commands)
#define PIN_MHZ19_RX    39   // ESP32 RX ← sensor TX (input-only, safe)
#define PIN_ANEMOMETER  27
#define PIN_RAIN_GAUGE  26
#define PIN_DS18B20     5

// ═══ Actuator Pins ═══
#define PIN_PUMP_MAIN   32
#define PIN_ZONE1       33
#define PIN_ZONE2       25
#define PIN_MISTING     14
#define PIN_FAN         12   // PWM
#define PIN_GROW_LIGHT  13   // PWM
#define PIN_FERTILIZER  15
#define PIN_PH_DOWN     2
#define PIN_PH_UP       16   // Moved from GPIO 0 (BOOT pin — unsafe for relay)
#define PIN_BUZZER      23
#define PIN_LED_R       18
#define PIN_LED_G       19
#define PIN_LED_B       4    // Moved from GPIO 21 (I2C SDA conflict)

// ═══ Calibration ═══
#define PH_VOLTAGE_4    2.03f
#define PH_VOLTAGE_7    1.51f
#define MOISTURE_DRY    3800
#define MOISTURE_WET    1200
#define ANEMOMETER_FACTOR 2.4f  // pulses/sec to km/h
#define RAIN_TIP_MM     0.2794f

// ═══ Timing ═══
#define SENSOR_READ_MS  5000
#define PUBLISH_MS      10000
#define WIFI_RETRY_MS   5000
#define MQTT_RETRY_MS   3000
#define WATCHDOG_TIMEOUT_MS 60000

// ═══ Buffers ═══
#define CIRCULAR_BUFFER_SIZE 60
#define PH_AVG_SAMPLES  10
#define DHT_RETRIES     3

// ═══ PWM ═══
#define PWM_FREQ        5000
#define PWM_RESOLUTION  8
#define FAN_CHANNEL      0
#define LIGHT_CHANNEL    1
#define LED_R_CHANNEL    2
#define LED_G_CHANNEL    3
#define LED_B_CHANNEL    4

// ═══ NTP (A-03) ═══
#define TIMEZONE_OFFSET_SEC  10800   // UTC+3 Iraq Standard Time (Baghdad/Basra)

// ═══ OTA (A-05) ═══
#define OTA_HOSTNAME    "agrimaster-esp32"
#define OTA_PASSWORD    "agrimaster2024"

#endif
