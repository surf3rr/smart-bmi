/*
 * Smart Attendance with Face Recognition - ESP32 Code
 * Hardware: ESP32, RC522 RFID Module
 * Works with Python Face Recognition Server
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <SPI.h>
#include <MFRC522.h>
#include <ArduinoJson.h>

// WiFi Credentials - CHANGE THESE
const char* ssid = "1puff";
const char* password = "meawmeaw";

// Server IP - CHANGE TO YOUR LAPTOP IP (find with ipconfig/ifconfig)
const char* serverIP = "http://10.91.188.245";  // CHANGE THIS!

// Pin Definitions for ESP32
#define SS_PIN 5       // RC522 SDA
#define RST_PIN 22     // RC522 RST
#define BUZZER_PIN 15  // Buzzer

// SPI Pins for ESP32 (using VSPI)
#define SCK_PIN 18     // SPI Clock
#define MISO_PIN 19    // SPI MISO
#define MOSI_PIN 23    // SPI MOSI

// Objects
MFRC522 rfid(SS_PIN, RST_PIN);

// State machine
enum State {
  WAIT_RFID,
  WAIT_FACE_VERIFY,
  PROCESSING
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
  Serial.println("║  SMART ATTENDANCE SYSTEM               ║");
  Serial.println("║  ESP32 + Face Recognition             ║");
  Serial.println("╚════════════════════════════════════════╝\n");
  
  // Pin modes
  pinMode(BUZZER_PIN, OUTPUT);
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
    Serial.println("\nCheck wiring:");
    Serial.println("  RC522 → ESP32");
    Serial.println("  SDA   → GPIO 5");
    Serial.println("  SCK   → GPIO 18");
    Serial.println("  MOSI  → GPIO 23");
    Serial.println("  MISO  → GPIO 19");
    Serial.println("  RST   → GPIO 22");
    Serial.println("  3.3V  → 3.3V (NOT 5V!)");
    Serial.println("  GND   → GND\n");
  } else {
    Serial.println("✓ RFID Reader ready");
  }
  
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
      
    case PROCESSING:
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
    Serial.println("Check your credentials and try again.");
  }
}

void handleRFIDScan() {
  // Look for new cards
  if (!rfid.PICC_IsNewCardPresent()) {
    return;
  }
  
  if (!rfid.PICC_ReadCardSerial()) {
    return;
  }
  
  // Read UID
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uid += "0";
    }
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  
  Serial.println("\n========================================");
  Serial.println("📇 RFID CARD DETECTED");
  Serial.println("========================================");
  Serial.print("🔑 UID: ");
  Serial.println(uid);
  
  // Card type
  MFRC522::PICC_Type piccType = rfid.PICC_GetType(rfid.uid.sak);
  Serial.print("📋 Type: ");
  Serial.println(rfid.PICC_GetTypeName(piccType));
  
  // Quick beep
  digitalWrite(BUZZER_PIN, HIGH);
  delay(50);
  digitalWrite(BUZZER_PIN, LOW);
  
  // Halt PICC
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  // Proceed to face verification
  currentRFID = uid;
  currentState = WAIT_FACE_VERIFY;
  lastActionTime = millis();
  
  Serial.println("\n👤 Starting face verification...");
  Serial.println("   Look at the camera!");
  
  sendRFIDToServer(uid);
}

void sendRFIDToServer(String uid) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi not connected!");
    beepFail();
    resetSystem();
    return;
  }
  
  HTTPClient http;
  String url = String(serverIP) + "/scan_rfid";
  
  Serial.print("📤 Sending to: ");
  Serial.println(url);
  
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(20000); // 20 second timeout for face verification
  
  // Create JSON payload
  StaticJsonDocument<200> doc;
  doc["rfid"] = uid;
  
  String jsonString;
  serializeJson(doc, jsonString);
  
  int httpResponseCode = http.POST(jsonString);
  
  Serial.print("📥 Response Code: ");
  Serial.println(httpResponseCode);
  
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.print("📄 Response: ");
    Serial.println(response);
    
    // Parse response
    StaticJsonDocument<512> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);
    
    if (!error) {
      String status = responseDoc["status"];
      String message = responseDoc["message"] | "";
      String name = responseDoc["name"] | "";
      
      if (status == "VERIFIED") {
        currentName = name;
        Serial.println("\n╔════════════════════════════════════════╗");
        Serial.println("║     ✓ ATTENDANCE MARKED!               ║");
        Serial.println("╚════════════════════════════════════════╝");
        Serial.print("👤 Welcome, ");
        Serial.println(name);
        Serial.print("🔑 RFID: ");
        Serial.println(uid);
        Serial.println("✓ Data sent to dashboard");
        Serial.println();
        
        beepSuccess();
        currentState = PROCESSING;
        
        // Auto reset after 3 seconds
        Serial.println("\nResetting in 3 seconds...");
        delay(3000);
        resetSystem();
        
      } else if (status == "NOT_REGISTERED") {
        Serial.println("\n╔════════════════════════════════════════╗");
        Serial.println("║     ⚠ RFID NOT REGISTERED              ║");
        Serial.println("╚════════════════════════════════════════╝");
        Serial.println("Please register this card first.");
        Serial.println("Run: python register.py");
        beepFail();
        resetSystem();
        
      } else {
        Serial.println("\n╔════════════════════════════════════════╗");
        Serial.println("║     ✗ VERIFICATION FAILED              ║");
        Serial.println("╚════════════════════════════════════════╝");
        if (message.length() > 0) {
          Serial.println(message);
        }
        beepFail();
        resetSystem();
      }
      
    } else {
      Serial.println("❌ JSON parsing failed!");
      Serial.println(error.c_str());
      beepFail();
      resetSystem();
    }
  } else {
    Serial.println("❌ HTTP Request Failed!");
    Serial.println("Possible issues:");
    Serial.println("  1. Server not running (python server.py)");
    Serial.println("  2. Wrong server IP address");
    Serial.println("  3. Firewall blocking connection");
    beepFail();
    resetSystem();
  }
  
  http.end();
}

void beepSuccess() {
  // Two happy beeps
  for (int i = 0; i < 2; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(100);
    digitalWrite(BUZZER_PIN, LOW);
    delay(100);
  }
}

void beepFail() {
  // One sad beep
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);
  digitalWrite(BUZZER_PIN, LOW);
}

void resetSystem() {
  currentState = WAIT_RFID;
  currentRFID = "";
  currentName = "";
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║       SYSTEM RESET                     ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.println("\n👉 Ready for next scan...\n");
}
