#include "sensors.h"
#include "config.h"
#include <DHT.h>
#include <Wire.h>
#include <BH1750.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_INA219.h>
#include <HardwareSerial.h>

// ═══ Globals ═══
static DHT dht(PIN_DHT22, DHT22);
static BH1750 lightMeter;
static OneWire oneWire(PIN_DS18B20);
static DallasTemperature ds18b20(&oneWire);
static Adafruit_INA219 ina219;
static HardwareSerial mhzSerial(1);

// Rain gauge interrupt counter
static volatile unsigned long rain_tips = 0;
static unsigned long last_rain_reset = 0;

// Wind pulse counter
static volatile unsigned long wind_pulses = 0;
static unsigned long last_wind_time = 0;

// pH averaging buffer
static float ph_readings[PH_AVG_SAMPLES];
static int ph_idx = 0;
static bool ph_filled = false;

// Sensor buffers for outlier detection
SensorBuffer buffers[10];

// C-10: Rain gauge with 20ms debounce
static volatile uint32_t last_rain_tip_ms = 0;

void IRAM_ATTR rain_isr() {
  uint32_t now = millis();
  if (now - last_rain_tip_ms > 20) {  // 20ms debounce
    rain_tips++;
    last_rain_tip_ms = now;
  }
}

void IRAM_ATTR wind_isr() {
  wind_pulses++;
}

void sensors_init() {
  // DHT22
  dht.begin();

  // I2C for BH1750 and INA219
  Wire.begin(PIN_BH1750_SDA, PIN_BH1750_SCL);
  lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  ina219.begin();

  // DS18B20
  ds18b20.begin();

  // MH-Z19B UART
  mhzSerial.begin(9600, SERIAL_8N1, PIN_MHZ19_RX, PIN_MHZ19_TX);

  // Soil moisture ADC
  analogSetAttenuation(ADC_11db);
  pinMode(PIN_SOIL_MOIST, INPUT);
  pinMode(PIN_PH, INPUT);

  // Rain gauge interrupt
  pinMode(PIN_RAIN_GAUGE, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_RAIN_GAUGE), rain_isr, FALLING);
  last_rain_reset = millis();

  // Anemometer interrupt
  pinMode(PIN_ANEMOMETER, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ANEMOMETER), wind_isr, FALLING);
  last_wind_time = millis();

  // Init buffers
  memset(buffers, 0, sizeof(buffers));

  Serial.println("[SENSORS] All sensors initialized");
}

// ═══ Buffer operations ═══
void sensors_push_buffer(SensorBuffer* buf, float val) {
  if (buf->count >= CIRCULAR_BUFFER_SIZE) {
    float old = buf->data[buf->head];
    buf->sum -= old;
    buf->sum_sq -= old * old;
  } else {
    buf->count++;
  }
  buf->data[buf->head] = val;
  buf->sum += val;
  buf->sum_sq += val * val;
  buf->head = (buf->head + 1) % CIRCULAR_BUFFER_SIZE;
}

float sensors_get_rolling_avg(SensorBuffer* buf) {
  if (buf->count == 0) return 0;
  return buf->sum / buf->count;
}

float sensors_get_rolling_std(SensorBuffer* buf) {
  if (buf->count < 2) return 0;
  float mean = buf->sum / buf->count;
  float variance = (buf->sum_sq / buf->count) - (mean * mean);
  return (variance > 0) ? sqrt(variance) : 0;
}

bool sensors_is_suspect(SensorBuffer* buf, float val, float sigma) {
  if (buf->count < 5) return false;
  float avg = sensors_get_rolling_avg(buf);
  float std = sensors_get_rolling_std(buf);
  if (std < 0.01) return false; // Too little variation to judge
  return fabs(val - avg) > (sigma * std);
}

// ═══ DHT22 — Temperature (with 3 retries) ═══
float read_dht22_temp() {
  for (int i = 0; i < DHT_RETRIES; i++) {
    float t = dht.readTemperature();
    if (!isnan(t)) return t;
    delay(100);
  }
  Serial.println("[SENSORS] DHT22 temp read failed after retries");
  return NAN;
}

// ═══ DHT22 — Humidity (with 3 retries) ═══
float read_dht22_humidity() {
  for (int i = 0; i < DHT_RETRIES; i++) {
    float h = dht.readHumidity();
    if (!isnan(h)) return h;
    delay(100);
  }
  Serial.println("[SENSORS] DHT22 humidity read failed after retries");
  return NAN;
}

// ═══ Soil Moisture — Capacitive (ADC → 0-100%) ═══
float read_soil_moisture() {
  long total = 0;
  for (int i = 0; i < 5; i++) {
    total += analogRead(PIN_SOIL_MOIST);
    delay(10);
  }
  int raw = total / 5;
  float pct = map(constrain(raw, MOISTURE_WET, MOISTURE_DRY),
                   MOISTURE_DRY, MOISTURE_WET, 0, 100);
  return constrain(pct, 0.0f, 100.0f);
}

// ═══ DS18B20 — Soil Temperature ═══
float read_soil_temp() {
  ds18b20.requestTemperatures();
  float t = ds18b20.getTempCByIndex(0);
  if (t == DEVICE_DISCONNECTED_C) {
    Serial.println("[SENSORS] DS18B20 disconnected");
    return NAN;
  }
  return t;
}

// ═══ pH — Two-point calibration with moving average ═══
float read_ph() {
  long total = 0;
  for (int i = 0; i < PH_AVG_SAMPLES; i++) {
    total += analogRead(PIN_PH);
    delay(10);
  }
  float voltage = (total / (float)PH_AVG_SAMPLES) * 3.3f / 4095.0f;

  // Two-point linear calibration: voltage → pH
  float slope = (7.0f - 4.0f) / (PH_VOLTAGE_7 - PH_VOLTAGE_4);
  float ph = 7.0f + slope * (voltage - PH_VOLTAGE_7);

  // Moving average
  ph_readings[ph_idx] = ph;
  ph_idx = (ph_idx + 1) % PH_AVG_SAMPLES;
  if (ph_idx == 0) ph_filled = true;

  int n = ph_filled ? PH_AVG_SAMPLES : ph_idx;
  float sum = 0;
  for (int i = 0; i < n; i++) sum += ph_readings[i];
  return constrain(sum / n, 0.0f, 14.0f);
}

// ═══ BH1750 — Light intensity (lux) ═══
float read_light() {
  unsigned long start = millis();
  float lux = lightMeter.readLightLevel();
  if (millis() - start > 500) {
    Serial.println("[SENSORS] BH1750 timeout");
    return NAN;
  }
  return (lux < 0) ? NAN : lux;
}

// ═══ MH-Z19B — CO2 (UART with checksum) ═══
float read_co2() {
  byte cmd[9] = {0xFF, 0x01, 0x86, 0, 0, 0, 0, 0, 0x79};
  while (mhzSerial.available()) mhzSerial.read(); // flush

  mhzSerial.write(cmd, 9);
  unsigned long start = millis();
  while (mhzSerial.available() < 9) {
    if (millis() - start > 1000) {
      Serial.println("[SENSORS] MH-Z19B timeout");
      return NAN;
    }
    delay(10);
  }

  byte resp[9];
  mhzSerial.readBytes(resp, 9);

  // Validate checksum
  byte checksum = 0;
  for (int i = 1; i < 8; i++) checksum += resp[i];
  checksum = 0xFF - checksum + 1;

  if (resp[0] != 0xFF || resp[1] != 0x86 || resp[8] != checksum) {
    Serial.println("[SENSORS] MH-Z19B checksum fail");
    return NAN;
  }
  return (float)(resp[2] * 256 + resp[3]);
}

// ═══ Anemometer — Pulse counting → km/h ═══
float read_wind_speed() {
  unsigned long now = millis();
  unsigned long elapsed = now - last_wind_time;
  if (elapsed < 1000) return 0;

  noInterrupts();
  unsigned long pulses = wind_pulses;
  wind_pulses = 0;
  interrupts();
  last_wind_time = now;

  float pps = (pulses * 1000.0f) / elapsed;
  return pps * ANEMOMETER_FACTOR;
}

// ═══ Rain Gauge — Tipping bucket (mm) ═══
float read_rainfall() {
  noInterrupts();
  unsigned long tips = rain_tips;
  interrupts();
  return tips * RAIN_TIP_MM;
}

// ═══ INA219 — Power consumption ═══
float read_power() {
  float voltage = ina219.getBusVoltage_V();
  float current = ina219.getCurrent_mA();
  if (isnan(voltage) || isnan(current)) return NAN;
  return (voltage * current) / 1000.0f; // Watts
}

// ═══ Read ALL sensors ═══
SensorReadings sensors_read_all() {
  SensorReadings r;
  memset(&r, 0, sizeof(r));

  r.temperature = read_dht22_temp();
  r.valid[0] = !isnan(r.temperature);

  r.humidity = read_dht22_humidity();
  r.valid[1] = !isnan(r.humidity);

  r.soil_moisture = read_soil_moisture();
  r.valid[2] = !isnan(r.soil_moisture);

  r.soil_temp = read_soil_temp();
  r.valid[3] = !isnan(r.soil_temp);

  r.ph = read_ph();
  r.valid[4] = !isnan(r.ph);

  r.light_lux = read_light();
  r.valid[5] = !isnan(r.light_lux);

  r.co2_ppm = read_co2();
  r.valid[6] = !isnan(r.co2_ppm);

  r.wind_kmh = read_wind_speed();
  r.valid[7] = true;

  r.rainfall_mm = read_rainfall();
  r.valid[8] = true;

  r.power_w = read_power();
  r.valid[9] = !isnan(r.power_w);

  return r;
}
