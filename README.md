# 🎓 Smart Attendance System
**RFID + Face Recognition** attendance tracking system using ESP32 and Python

---

## 📋 System Overview

```
┌──────────────┐         ┌────────────────────┐         ┌─────────────┐
│   ESP32      │  WiFi   │  Python Server     │   USB   │   Webcam    │
│   + RFID     │────────>│  (Flask + OpenCV)  │<────────│             │
│   + Buzzer   │         │  + Face Recognition│         └─────────────┘
└──────────────┘         └────────────────────┘
       │                           │
       │                           ├─> Dashboard (Web UI)
       │                           ├─> User Database
       │                           └─> Attendance Records
       │
    RFID Card
```

### How It Works:
1. **User scans RFID card** on ESP32 reader
2. **ESP32 sends RFID** to Python server via WiFi
3. **Server captures face** from webcam
4. **Face Recognition** verifies identity matches RFID
5. **Attendance marked** and displayed on dashboard
6. **ESP32 beeps** (success = 2 beeps, fail = 1 long beep)

---

## 🛠️ Hardware Requirements

### ESP32 Setup:
- **ESP32 Development Board**
- **RC522 RFID Module**
- **Buzzer** (optional but recommended)
- **Jumper Wires**

### Wiring:
```
RC522 → ESP32
─────────────
SDA   → GPIO 5
SCK   → GPIO 18
MOSI  → GPIO 23
MISO  → GPIO 19
RST   → GPIO 22
3.3V  → 3.3V (⚠️ NOT 5V!)
GND   → GND

Buzzer → ESP32
─────────────
+     → GPIO 15
-     → GND
```

---

## 💻 Software Requirements

### Python Server (Laptop/PC):
- Python 3.8 or higher
- Webcam (USB or built-in)
- Windows/Linux/macOS

### Libraries:
Install all dependencies:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install flask opencv-python face-recognition numpy cmake dlib
```

---

## 🚀 Setup Instructions

### Step 1: Setup Python Environment

```bash
# Clone or download the project
cd smart-attendance-system

# Install dependencies
pip install -r requirements.txt

# Create data directory (will be auto-created)
mkdir data
```

### Step 2: Register Users

```bash
python register.py
```

**Registration Process:**
1. Select option 1 (Register new user)
2. Enter user's name
3. Scan RFID card with ESP32 (get UID from Serial Monitor)
4. Enter the RFID UID
5. Look at webcam and press SPACE to capture face
6. User is registered!

**Tips for good face capture:**
- Good lighting
- Face the camera directly
- Remove glasses if possible
- Neutral expression
- Only one person in frame

### Step 3: Upload ESP32 Code

1. Open `esp32_rfid_face_attendance.ino` in Arduino IDE
2. **IMPORTANT**: Update these lines:
   ```cpp
   const char* ssid = "YOUR_WIFI_NAME";
   const char* password = "YOUR_WIFI_PASSWORD";
   const char* serverIP = "http://YOUR_LAPTOP_IP";  // e.g., "http://192.168.1.100"
   ```
3. Find your laptop IP:
   - **Windows**: `ipconfig` (look for IPv4 Address)
   - **Linux/Mac**: `ifconfig` or `ip addr`
4. Upload code to ESP32
5. Open Serial Monitor (115200 baud)

### Step 4: Start the Server

```bash
python server.py
```

You should see:
```
════════════════════════════════════════════════════════════
  SMART ATTENDANCE SYSTEM - SERVER
════════════════════════════════════════════════════════════
✓ Loaded X registered users
✓ Loaded Y attendance records

📋 Server Configuration:
   Host: 0.0.0.0
   Port: 5000
   Registered Users: X
   Attendance Records: Y

🌐 Access Points:
   Dashboard: http://localhost:5000
   API Stats: http://localhost:5000/api/stats
   Health Check: http://localhost:5000/health

🚀 Starting server...
════════════════════════════════════════════════════════════
```

### Step 5: Open Dashboard

Open your browser and go to:
```
http://localhost:5000
```

You'll see:
- Total Users
- Today's Attendance
- Total Records
- Recent Attendance Table
- Registered Users List

---

## 📱 Usage

### Taking Attendance:

1. **Scan RFID card** on ESP32 reader
   - You'll hear a quick beep
   - ESP32 LED might blink
   
2. **Look at the webcam** immediately
   - Server captures your face
   - Face recognition runs (takes 2-5 seconds)
   
3. **Results:**
   - ✅ **Success**: 2 happy beeps, attendance marked
   - ❌ **Fail**: 1 long sad beep, try again

### What appears on dashboard:
- Name
- RFID UID
- Timestamp (date & time)
- Status: Present

---

## 📊 Dashboard Features

### Statistics Cards:
- 👥 **Total Users**: Number of registered users
- 📅 **Today's Attendance**: Attendance marked today
- 📋 **Total Records**: All-time attendance records

### Recent Attendance Table:
- Name & RFID
- Date & Time
- Status badge
- Auto-refreshes every 5 seconds

### Registered Users List:
- Shows all registered users
- Name with avatar
- RFID UID

---

## 🔧 Troubleshooting

### ESP32 Issues:

**RFID not working (0x00 or 0xFF firmware):**
- Check wiring (especially 3.3V NOT 5V!)
- Try different SPI pins
- Ensure RC522 module is genuine

**WiFi not connecting:**
- Check SSID and password
- Ensure 2.4GHz WiFi (not 5GHz)
- Check ESP32 has WiFi antenna

**HTTP request fails:**
- Verify server IP address
- Check firewall (allow port 5000)
- Ensure server is running

### Python Server Issues:

**Camera not opening:**
```bash
# Linux: Install v4l-utils
sudo apt-get install v4l-utils

# Check camera
ls /dev/video*

# Test camera
python -c "import cv2; print(cv2.VideoCapture(0).read())"
```

**Face recognition not working:**
- Improve lighting
- Face camera directly
- Try lower `FACE_MATCH_THRESHOLD` in server.py (line 22)

**Import errors:**
```bash
# dlib issues on Windows:
pip install cmake
pip install dlib==19.24.2

# If still fails, use pre-built wheel:
# Download from: https://github.com/z-mahmud22/Dlib_Windows_Python3.x
```

### Dashboard Issues:

**No data showing:**
- Check server is running
- Open browser console (F12) for errors
- Verify API endpoints work: http://localhost:5000/health

---

## 📁 File Structure

```
smart-attendance-system/
│
├── esp32_rfid_face_attendance.ino  # ESP32 Arduino code
├── server.py                        # Main Flask server
├── register.py                      # User registration tool
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
│
├── templates/
│   └── dashboard.html              # Web dashboard
│
└── data/                           # Created automatically
    ├── users.json                  # Registered users & faces
    └── attendance.json             # Attendance records
```

---

## 🔐 Security Notes

- Face data is stored locally (not in cloud)
- RFID UIDs are not encrypted (consider adding encryption for production)
- Server runs on local network (not exposed to internet)
- No passwords stored

---

## 🎯 Features

✅ RFID card scanning  
✅ Face recognition verification  
✅ Real-time dashboard  
✅ Auto-refresh every 5 seconds  
✅ Attendance history  
✅ User management  
✅ Audio feedback (buzzer)  
✅ Timeout handling  
✅ Error handling  

---

## 🔮 Future Enhancements

- [ ] MySQL/PostgreSQL database support
- [ ] Multiple camera support
- [ ] SMS/Email notifications
- [ ] Export to Excel/PDF
- [ ] Admin panel
- [ ] Mobile app
- [ ] Cloud sync
- [ ] Anti-spoofing (liveness detection)

---

## 📝 API Endpoints

### ESP32 Endpoints:
- `POST /scan_rfid` - Verify RFID + Face
  ```json
  Request: {"rfid": "A1B2C3D4"}
  Response: {"status": "VERIFIED", "name": "John Doe"}
  ```

### Dashboard Endpoints:
- `GET /` - Dashboard HTML
- `GET /api/stats` - Statistics
- `GET /api/users` - All users
- `GET /api/attendance` - All records
- `GET /health` - Server health check

---

## 🤝 Contributing

Feel free to fork, improve, and submit pull requests!

---

## 📄 License

MIT License - Free to use and modify

---

## 👨‍💻 Support

For issues or questions, please check the troubleshooting section above.

---

**Made with ❤️ for smart attendance tracking**
