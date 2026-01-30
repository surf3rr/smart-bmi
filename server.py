"""
Smart Attendance System - Python Server
Handles RFID verification with face recognition
Stores attendance data and serves dashboard
"""

from flask import Flask, request, jsonify, render_template
import cv2
import face_recognition
import numpy as np
import json
import os
from datetime import datetime
import threading
import time

app = Flask(__name__)

# File paths
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.json")

# Create data directory if it doesn't exist
os.makedirs(DATA_DIR, exist_ok=True)

# Global data
users = {}  # {rfid: {name, face_encoding}}
attendance_records = []

# Face verification settings
FACE_MATCH_THRESHOLD = 0.6  # Lower = stricter
FACE_CAPTURE_ATTEMPTS = 30  # Number of frames to try
FACE_CAPTURE_DELAY = 0.1    # Delay between captures

def load_data():
    """Load users and attendance from JSON files"""
    global users, attendance_records
    
    # Load users
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            # Convert face encodings back to numpy arrays
            for rfid, user_data in data.items():
                users[rfid] = {
                    'name': user_data['name'],
                    'face_encoding': np.array(user_data['face_encoding'])
                }
        print(f"✓ Loaded {len(users)} registered users")
    else:
        print("⚠ No users file found. Please register users first.")
    
    # Load attendance
    if os.path.exists(ATTENDANCE_FILE):
        with open(ATTENDANCE_FILE, 'r') as f:
            attendance_records = json.load(f)
        print(f"✓ Loaded {len(attendance_records)} attendance records")
    else:
        attendance_records = []
        print("⚠ No attendance file found. Starting fresh.")

def save_users():
    """Save users to JSON file"""
    data = {}
    for rfid, user_data in users.items():
        data[rfid] = {
            'name': user_data['name'],
            'face_encoding': user_data['face_encoding'].tolist()
        }
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✓ Saved {len(users)} users")

def save_attendance():
    """Save attendance to JSON file"""
    with open(ATTENDANCE_FILE, 'w') as f:
        json.dump(attendance_records, f, indent=2)
    print(f"✓ Saved attendance record")

def capture_face():
    """Capture face from webcam and return face encoding"""
    print("📷 Opening camera...")
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        print("❌ Could not open camera!")
        return None, "Camera not accessible"
    
    # Give camera time to warm up
    time.sleep(1)
    
    face_encoding = None
    attempts = 0
    
    print("👤 Looking for face...")
    
    while attempts < FACE_CAPTURE_ATTEMPTS and face_encoding is None:
        ret, frame = camera.read()
        
        if not ret:
            attempts += 1
            time.sleep(FACE_CAPTURE_DELAY)
            continue
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Find faces
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) == 0:
            attempts += 1
            time.sleep(FACE_CAPTURE_DELAY)
            continue
        
        if len(face_locations) > 1:
            print("⚠ Multiple faces detected. Please ensure only one person is visible.")
            attempts += 1
            time.sleep(FACE_CAPTURE_DELAY)
            continue
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        if len(face_encodings) > 0:
            face_encoding = face_encodings[0]
            print("✓ Face captured successfully!")
            break
        
        attempts += 1
        time.sleep(FACE_CAPTURE_DELAY)
    
    camera.release()
    
    if face_encoding is None:
        return None, "No face detected. Please look at the camera."
    
    return face_encoding, None

def verify_face(captured_encoding, registered_encoding):
    """Compare two face encodings"""
    distance = face_recognition.face_distance([registered_encoding], captured_encoding)[0]
    match = distance < FACE_MATCH_THRESHOLD
    
    print(f"Face distance: {distance:.3f} (threshold: {FACE_MATCH_THRESHOLD})")
    
    return match, distance

@app.route('/')
def dashboard():
    """Serve the dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats')
def get_stats():
    """Get statistics for dashboard"""
    total_users = len(users)
    total_attendance = len(attendance_records)
    
    # Get today's attendance
    today = datetime.now().strftime('%Y-%m-%d')
    today_attendance = [r for r in attendance_records if r['date'] == today]
    
    return jsonify({
        'total_users': total_users,
        'total_attendance': total_attendance,
        'today_attendance': len(today_attendance),
        'recent_records': attendance_records[-10:][::-1]  # Last 10, reversed
    })

@app.route('/api/users')
def get_users():
    """Get all registered users"""
    user_list = []
    for rfid, data in users.items():
        user_list.append({
            'rfid': rfid,
            'name': data['name']
        })
    return jsonify(user_list)

@app.route('/api/attendance')
def get_attendance():
    """Get all attendance records"""
    return jsonify(attendance_records[::-1])  # Newest first

@app.route('/scan_rfid', methods=['POST'])
def scan_rfid():
    """
    ESP32 sends RFID, server verifies face
    """
    try:
        data = request.json
        rfid = data.get('rfid', '').upper()
        
        print("\n" + "="*50)
        print(f"📇 RFID Scan Received: {rfid}")
        print("="*50)
        
        # Check if RFID is registered
        if rfid not in users:
            print("❌ RFID not registered")
            return jsonify({
                'status': 'NOT_REGISTERED',
                'message': 'This RFID card is not registered. Please register first.'
            })
        
        user_name = users[rfid]['name']
        print(f"✓ RFID registered to: {user_name}")
        
        # Capture face from camera
        print("\n👤 Starting face verification...")
        captured_encoding, error = capture_face()
        
        if error:
            print(f"❌ Face capture failed: {error}")
            return jsonify({
                'status': 'FAILED',
                'message': error
            })
        
        # Verify face matches registered face
        registered_encoding = users[rfid]['face_encoding']
        match, distance = verify_face(captured_encoding, registered_encoding)
        
        if match:
            print(f"✅ FACE VERIFIED for {user_name}!")
            
            # Record attendance
            attendance_record = {
                'rfid': rfid,
                'name': user_name,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'status': 'Present'
            }
            
            attendance_records.append(attendance_record)
            save_attendance()
            
            print(f"✓ Attendance marked at {attendance_record['timestamp']}")
            print("="*50 + "\n")
            
            return jsonify({
                'status': 'VERIFIED',
                'name': user_name,
                'message': f'Welcome, {user_name}! Attendance marked.'
            })
        
        else:
            print(f"❌ FACE MISMATCH (distance: {distance:.3f})")
            print(f"   Expected: {user_name}")
            print(f"   Detected: Unknown person")
            print("="*50 + "\n")
            
            return jsonify({
                'status': 'FAILED',
                'message': 'Face verification failed. The face does not match the registered user.'
            })
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({
            'status': 'ERROR',
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'OK',
        'users': len(users),
        'attendance': len(attendance_records)
    })

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  SMART ATTENDANCE SYSTEM - SERVER")
    print("="*60)
    
    # Load existing data
    load_data()
    
    print("\n📋 Server Configuration:")
    print(f"   Host: 0.0.0.0 (accessible from network)")
    print(f"   Port: 5000")
    print(f"   Registered Users: {len(users)}")
    print(f"   Attendance Records: {len(attendance_records)}")
    
    print("\n🌐 Access Points:")
    print("   Dashboard: http://localhost:5000")
    print("   API Stats: http://localhost:5000/api/stats")
    print("   Health Check: http://localhost:5000/health")
    
    print("\n⚠️  IMPORTANT:")
    print("   1. Make sure your webcam is connected")
    print("   2. Update ESP32 with this computer's IP address")
    print("   3. Register users first: python register.py")
    
    print("\n" + "="*60)
    print("🚀 Starting server...")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
