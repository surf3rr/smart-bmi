/*
 * Smart Attendance + BMI OPD Screener - ESP32 Code
 * Hardware: ESP32, RC522 RFID, HX711 Load Cells, Buzzer, Button
 * Works with Python Face Recognition Server
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
// #include <HX711.h>   // COMMENTED - Weight module disabled
#include <ArduinoJson.h>

// WiFi Credentials - CHANGE THESE
const char* ssid = "1puff";
const char* password = "meawmeaw";

// Server IP - CHANGE TO YOUR LAPTOP IP (find with ipconfig/ifconfig)
const char* serverIP = "http://10.91.188.245:5000";

// Pin Definitions for ESP32
#define SS_PIN 5       // RC522 SDA
#define RST_PIN 22     // RC522 RST
#define BUZZER_PIN 15  // Buzzer
#define BUTTON_PIN 13  // Push Button
#define HX711_DT 4     // HX711 Data
#define HX711_SCK 2    // HX711 Clock

// SPI Pins for ESP32 (using VSPI)
#define SCK_PIN 18     // SPI Clock
#define MISO_PIN 19    // SPI MISO
#define MOSI_PIN 23    // SPI MOSI

// Objects
MFRC522 rfid(SS_PIN, RST_PIN);
// HX711 scale;   // COMMENTED - Weight module disabled

// Calibration factor for HX711 - ADJUST THIS
// float calibration_factor = -7050; // COMMENTED - Weight module disabled

// State machine
enum State {
  WAIT_RFID,
  WAIT_FACE_VERIFY,
  WAIT_WEIGHT,
  SEND_WEIGHT
};

State currentState = WAIT_RFID;
String currentRFID = "";
String currentName = "";
unsigned long lastActionTime = 0;
const unsigned long TIMEOUT = 30000; // 30 second timeout

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n╔════════════════════════════════════════╗");
  Serial.println("║  SMART ATTENDANCE & BMI SYSTEM         ║");
  Serial.println("║  ESP32 + Face Recognition             ║");
  Serial.println("╚════════════════════════════════════════╝\n");
  
  // Pin modes
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  digitalWrite(BUZZER_PIN, LOW);
  
  // Initialize SPI
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
  Serial.println("✓ SPI initialized");
  delay(100);
  
  // Initialize RFID
  rfid.PCD_Init();
  delay(100);
  
  // Check RFID reader
  byte version = rfid.PCD_ReadRegister(rfid.VersionReg);
  Serial.print("MFRC522 Firmware: 0x");
  Serial.println(version, HEX);
  
  if (version == 0x00 || version == 0xFF) {
    Serial.println("\n⚠ WARNING: RFID Communication Problem!");
  } else {
    Serial.println("✓ RFID Reader ready");
  }
  
  // Initialize HX711
  /*
  scale.begin(HX711_DT, HX711_SCK);
  scale.set_scale(calibration_factor);
  scale.tare();
  Serial.println("✓ Scale initialized and tared");
  */

  // Connect to WiFi
  connectWiFi();
  
  // Test beep
  digitalWrite(BUZZER_PIN, HIGH);
  delay(100);
  digitalWrite(BUZZER_PIN, LOW);
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║         SYSTEM READY!                  ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.println("\n👉 Scan your RFID card to begin...\n");
}

void loop() {
  // Check WiFi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠ WiFi lost. Reconnecting...");
    connectWiFi();
  }
  
  // State machine
  switch (currentState) {
    case WAIT_RFID:
      handleRFIDScan();
      break;
      
    case WAIT_FACE_VERIFY:
      if (millis() - lastActionTime > TIMEOUT) {
        Serial.println("\n⏱ Timeout! Face verification took too long.");
        beepFail();
        resetSystem();
      }
      break;
      
    case WAIT_WEIGHT:
      // handleWeightMeasurement();   // COMMENTED - Weight module disabled
      break;
      
    case SEND_WEIGHT:
      // Waiting for reset
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
    Serial.print("📡 IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("🖥️  Server: ");
    Serial.println(serverIP);
  } else {
    Serial.println("\n❌ WiFi Connection Failed!");
  }
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
  
  Serial.print("UID: ");
  Serial.println(uid);
  
  digitalWrite(BUZZER_PIN, HIGH);
  delay(50);
  digitalWrite(BUZZER_PIN, LOW);
  
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  currentRFID = uid;
  currentState = WAIT_FACE_VERIFY;
  lastActionTime = millis();
  
  Serial.println("Starting face verification...");
  sendRFIDToServer(uid);
}

void sendRFIDToServer(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    beepFail();
    resetSystem();
    return;
  }
  
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
        
        // currentState = WAIT_WEIGHT;   // COMMENTED - Weight step skipped
        
        Serial.println("Face Verified - Process Complete");
        delay(2000);
        resetSystem();
      } else {
        beepFail();
        resetSystem();
      }
    }
  } else {
    beepFail();
    resetSystem();
  }
  
  http.end();
}

/*
void handleWeightMeasurement() {
   COMMENTED - Weight module disabled
}

void sendWeightToServer(String uid, float weight) {
   COMMENTED - Weight module disabled
}
*/

void beepSuccess() {
  for (int i = 0; i < 2; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
  }
}

void beepFail() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);
  digitalWrite(BUZZER_PIN, LOW);
}

void resetSystem() {
  currentState = WAIT_RFID;
  currentRFID = "";
  currentName = "";
  
  Serial.println("\nSYSTEM RESET");
}
