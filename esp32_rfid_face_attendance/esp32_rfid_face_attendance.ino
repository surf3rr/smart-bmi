/*
 * Smart Attendance + BMI OPD Screener - ESP32 Code
 * Hardware: ESP32, RC522 RFID, HC-SR04 Ultrasonic, Buzzer, Button
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ArduinoJson.h>

// WiFi Credentials
const char* ssid = "1puff";
const char* password = "meawmeaw";
const char* serverIP = "http://10.198.230.245:5000";

// RFID Pins
#define SS_PIN 5
#define RST_PIN 22
#define SCK_PIN 18
#define MISO_PIN 19
#define MOSI_PIN 23

// Buzzer & Button
#define BUZZER_PIN 15
#define BUTTON_PIN 13

// HC-SR04 Ultrasonic Sensor Pins
#define TRIG_PIN 4
#define ECHO_PIN 21

// Sensor mount height in cm (distance from sensor to floor when nobody standing)
// Measure this physically and update accordingly
#define SENSOR_HEIGHT_CM 220.0

MFRC522 rfid(SS_PIN, RST_PIN);

enum State {
  WAIT_RFID,
  WAIT_FACE_VERIFY,
  MEASURE_HEIGHT,
  SEND_DATA
};

State currentState = WAIT_RFID;
String currentRFID = "";
String currentName = "";
float measuredHeight = 0.0;
unsigned long lastActionTime = 0;
const unsigned long TIMEOUT = 30000;

void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║  SMART ATTENDANCE & BMI SYSTEM         ║");
  Serial.println("╚════════════════════════════════════════╝\n");

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(BUZZER_PIN, LOW);

  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
  rfid.PCD_Init();
  delay(100);

  byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("MFRC522 Firmware: 0x");
  Serial.println(version, HEX);
  if (version == 0x00 || version == 0xFF)
    Serial.println("⚠ WARNING: RFID Communication Problem!");
  else
    Serial.println("✓ RFID Reader ready");

  Serial.println("✓ HC-SR04 Ultrasonic ready");

  connectWiFi();

  // Test beep
  digitalWrite(BUZZER_PIN, HIGH); delay(100); digitalWrite(BUZZER_PIN, LOW);

  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║         SYSTEM READY!                  ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.println("\n👉 Scan your RFID card to begin...\n");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠ WiFi lost. Reconnecting...");
    connectWiFi();
  }

  switch (currentState) {
    case WAIT_RFID:
      handleRFIDScan();
      break;

    case WAIT_FACE_VERIFY:
      if (millis() - lastActionTime > TIMEOUT) {
        Serial.println("⏱ Timeout! Face verification took too long.");
        beepFail();
        resetSystem();
      }
      break;

    case MEASURE_HEIGHT:
      handleHeightMeasurement();
      break;

    case SEND_DATA:
      break;
  }

  delay(50);
}

void connectWiFi() {
  Serial.print("\n🔌 Connecting to WiFi");
  WiFi.begin(ssid, password);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println(" Connected!");
    Serial.print("📡 IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WiFi Connection Failed!");
  }
}

float measureDistance() {
  // Take 5 readings and average for stability
  float total = 0;
  int valid = 0;
  for (int i = 0; i < 5; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout
    if (duration > 0) {
      float dist = (duration * 0.0343) / 2.0;
      total += dist;
      valid++;
    }
    delay(50);
  }
  return (valid > 0) ? (total / valid) : -1;
}

void handleHeightMeasurement() {
  Serial.println("\n📏 Measuring height... Please stand still under the sensor.");
  beepSuccess(); // Signal to stand

  delay(2000); // Wait for person to position

  float distanceCm = measureDistance();

  if (distanceCm < 0 || distanceCm > SENSOR_HEIGHT_CM) {
    Serial.println("❌ Height measurement failed. No person detected.");
    beepFail();
    resetSystem();
    return;
  }

  measuredHeight = SENSOR_HEIGHT_CM - distanceCm;

  // Sanity check: valid human height range 100cm - 220cm
  if (measuredHeight < 100 || measuredHeight > 220) {
    Serial.print("❌ Invalid height reading: ");
    Serial.println(measuredHeight);
    beepFail();
    resetSystem();
    return;
  }

  Serial.print("✅ Height measured: ");
  Serial.print(measuredHeight);
  Serial.println(" cm");

  // Send height to server (weight will be entered manually on dashboard)
  sendHeightToServer(currentRFID, measuredHeight);
}

void handleRFIDScan() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  Serial.print("\n📇 RFID Scanned: "); Serial.println(uid);
  digitalWrite(BUZZER_PIN, HIGH); delay(50); digitalWrite(BUZZER_PIN, LOW);

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  currentRFID = uid;
  currentState = WAIT_FACE_VERIFY;
  lastActionTime = millis();

  sendRFIDToServer(uid);
}

void sendRFIDToServer(String uid) {
  if (WiFi.status() != WL_CONNECTED) { beepFail(); resetSystem(); return; }

  HTTPClient http;
  String url = String(serverIP) + "/scan_rfid";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(20000);

  StaticJsonDocument<200> doc;
  doc["rfid"] = uid;
  String jsonString;
  serializeJson(doc, jsonString);

  int httpResponseCode = http.POST(jsonString);

  if (httpResponseCode > 0) {
    String response = http.getString();
    StaticJsonDocument<512> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);

    if (!error) {
      String status = responseDoc["status"];
      String name = responseDoc["name"] | "";

      if (status == "VERIFIED") {
        currentName = name;
        beepSuccess();
        Serial.println("✅ Face Verified! Proceeding to height measurement...");
        currentState = MEASURE_HEIGHT;
        lastActionTime = millis();
      } else {
        Serial.println("❌ Verification failed.");
        beepFail();
        resetSystem();
      }
    }
  } else {
    Serial.println("❌ HTTP Error");
    beepFail();
    resetSystem();
  }
  http.end();
}

void sendHeightToServer(String uid, float height) {
  if (WiFi.status() != WL_CONNECTED) { beepFail(); resetSystem(); return; }

  HTTPClient http;
  String url = String(serverIP) + "/submit_height";
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(10000);

  StaticJsonDocument<200> doc;
  doc["rfid"] = uid;
  doc["height"] = height;
  String jsonString;
  serializeJson(doc, jsonString);

  int httpResponseCode = http.POST(jsonString);

  if (httpResponseCode > 0) {
    Serial.println("✅ Height sent to server.");
    beepSuccess();
  } else {
    Serial.println("❌ Failed to send height.");
    beepFail();
  }
  http.end();
  delay(1000);
  resetSystem();
}

void beepSuccess() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(100);
    digitalWrite(BUZZER_PIN, LOW);  delay(100);
  }
}

void beepFail() {
  digitalWrite(BUZZER_PIN, HIGH); delay(500); digitalWrite(BUZZER_PIN, LOW);
}

void resetSystem() {
  currentState = WAIT_RFID;
  currentRFID = "";
  currentName = "";
  measuredHeight = 0.0;
  Serial.println("\n🔄 SYSTEM RESET - Scan card to begin...\n");
}