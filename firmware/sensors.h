#ifndef SENSORS_H
#define SENSORS_H

#include <Arduino.h>

struct SensorReadings {
  float temperature;
  float humidity;
  float soil_moisture;
  float soil_temp;
  float ph;
  float light_lux;
  float co2_ppm;
  float wind_kmh;
  float rainfall_mm;
  float power_w;
  bool valid[10]; // validity flag per sensor
};

// Circular buffer for outlier detection
struct SensorBuffer {
  float data[60];
  int head;
  int count;
  float sum;
  float sum_sq;
};

void sensors_init();
SensorReadings sensors_read_all();
float sensors_get_rolling_avg(SensorBuffer* buf);
float sensors_get_rolling_std(SensorBuffer* buf);
void sensors_push_buffer(SensorBuffer* buf, float val);
bool sensors_is_suspect(SensorBuffer* buf, float val, float sigma);

// Individual sensor reads
float read_dht22_temp();
float read_dht22_humidity();
float read_soil_moisture();
float read_soil_temp();
float read_ph();
float read_light();
float read_co2();
float read_wind_speed();
float read_rainfall();
float read_power();

// Interrupt handler for rain gauge
void IRAM_ATTR rain_isr();

#endif
