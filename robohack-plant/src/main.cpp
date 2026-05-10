#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// true = human-readable prototyping output, false = compact pyserial format
const bool PROTO_MODE = false;

#define LDR_PIN       4
#define TEMP_PIN      5
#define MOISTURE_A0   6
#define LED1_R        16
#define LED1_G        15
#define LED1_B        17
#define LED2_R        18
#define LED2_G        19
#define LED2_B        20
#define BAND_R        35
#define BAND_B        36

OneWire oneWire(TEMP_PIN);
DallasTemperature tempSensor(&oneWire);

void setColorLED1(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(LED1_R, r);
  analogWrite(LED1_G, g);
  analogWrite(LED1_B, b);
}

void setColorLED2(uint8_t r, uint8_t g, uint8_t b) {
  analogWrite(LED2_R, r);
  analogWrite(LED2_G, g);
  analogWrite(LED2_B, b);
}

void setColorBand(uint8_t r, uint8_t b) {
  analogWrite(BAND_R, 255 - r);  // common anode: 0V = on, 5V = off
  analogWrite(BAND_B, 255 - b);
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  pinMode(LED1_R, OUTPUT);
  pinMode(LED1_G, OUTPUT);
  pinMode(LED1_B, OUTPUT);
  pinMode(LED2_R, OUTPUT);
  pinMode(LED2_G, OUTPUT);
  pinMode(LED2_B, OUTPUT);
  pinMode(BAND_R, OUTPUT);
  pinMode(BAND_B, OUTPUT);
  tempSensor.begin();
  tempSensor.setResolution(9);
  tempSensor.setWaitForConversion(false);
  tempSensor.requestTemperatures();
}

void loop() {
  static int oldTime=millis();
  int newTime=millis();
  if (newTime-oldTime>500){
  // Luminosity
  int ldrRaw = analogRead(LDR_PIN);
  int lux_pct = constrain(map(ldrRaw, 4095, 0, 0, 100), 0, 100);

  // Temperature
  float tempC = tempSensor.getTempCByIndex(0);
  tempSensor.requestTemperatures();

  // Soil moisture
  int moistureRaw = analogRead(MOISTURE_A0);
  int moisture_pct = constrain(map(moistureRaw, 4095, 0, 0, 100), 0, 100);

  // LED1: temperature
  const char* tempColor;
  if (tempC < 20.0) {
    setColorLED1(0, 255, 0);
    tempColor = "GREEN";
  } else if (tempC <= 25.0) {
    setColorLED1(255, 165, 0);
    tempColor = "ORANGE";
  } else {
    setColorLED1(255, 0, 0);
    tempColor = "RED";
  }

  // LED2: smooth moisture gradient red -> orange -> green
  uint8_t mr, mg;
  if (moisture_pct <= 50) {
    float t = moisture_pct / 50.0;
    mr = 255;
    mg = (uint8_t)(255 * t);
  } else {
    float t = (moisture_pct - 50) / 50.0;
    mr = (uint8_t)(255 * (1.0 - t));
    mg = 255;
  }
  setColorLED2(mr, mg, 0);

  // LED band: full purple below 80% light, fully off at 85%+
  uint8_t bandIntensity = (lux_pct < 80) ? 255 : 0;
  setColorBand(bandIntensity, bandIntensity);

  if (PROTO_MODE) {
    Serial.printf(
      "Light: %d%% | Temp: %.1f°C [%s] | Moisture: %d%%\n",
      lux_pct, tempC, tempColor, moisture_pct
    );
  } else {
    // FORMAT: light(%),temp(°C),moisture(%)
    // Fields: int, float(1dp), int
    // Example: 90,26.5,44
    Serial.printf("%d,%.1f,%d\n", lux_pct, tempC, moisture_pct);
  }
  oldTime=newTime;
  }

}