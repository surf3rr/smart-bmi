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
users = {}              # {rfid: {name, face_encoding}}
attendance_records = [] # list of attendance dicts
pending_bmi = {}        # {rfid: {name, height, timestamp}} — waiting for weight input

# Face verification settings
FACE_MATCH_THRESHOLD = 0.6
FACE_CAPTURE_ATTEMPTS = 30
FACE_CAPTURE_DELAY = 0.1


# ─────────────────────────────────────────────────────────────
# DATA PERSISTENCE
# ─────────────────────────────────────────────────────────────

def load_data():
    """Load users and attendance from JSON files"""
    global users, attendance_records

    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            for rfid, user_data in data.items():
                users[rfid] = {
                    'name': user_data['name'],
                    'face_encoding': np.array(user_data['face_encoding'])
                }
        print(f"✓ Loaded {len(users)} registered users")
    else:
        print("⚠ No users file found. Please register users first.")

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


# ─────────────────────────────────────────────────────────────
# FACE RECOGNITION HELPERS
# ─────────────────────────────────────────────────────────────

def capture_face():
    """Capture face from webcam and return face encoding"""
    print("📷 Opening camera...")
    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("❌ Could not open camera!")
        return None, "Camera not accessible"

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

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)

        if len(face_locations) == 0:
            attempts += 1
            time.sleep(FACE_CAPTURE_DELAY)
            continue

        if len(face_locations) > 1:
            print("⚠ Multiple faces detected.")
            attempts += 1
            time.sleep(FACE_CAPTURE_DELAY)
            continue

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


# ─────────────────────────────────────────────────────────────
# ROUTES — DASHBOARD
# ─────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    return render_template('dashboard.html')


@app.route('/api/stats')
def get_stats():
    total_users = len(users)
    total_attendance = len(attendance_records)
    today = datetime.now().strftime('%Y-%m-%d')
    today_attendance = [r for r in attendance_records if r['date'] == today]

    return jsonify({
        'total_users': total_users,
        'total_attendance': total_attendance,
        'today_attendance': len(today_attendance),
        'recent_records': attendance_records[-10:][::-1]
    })


@app.route('/api/users')
def get_users():
    user_list = [{'rfid': rfid, 'name': data['name']} for rfid, data in users.items()]
    return jsonify(user_list)


@app.route('/api/attendance')
def get_attendance():
    return jsonify(attendance_records[::-1])


# ─────────────────────────────────────────────────────────────
# ROUTES — ESP32 ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.route('/scan_rfid', methods=['POST'])
def scan_rfid():
    """ESP32 sends RFID → server does face verification → records attendance"""
    try:
        data = request.json
        rfid = data.get('rfid', '').upper().strip()

        print("\n" + "="*50)
        print(f"📇 RFID Scan Received: {rfid}")
        print("="*50)

        if rfid not in users:
            print("❌ RFID not registered")
            return jsonify({
                'status': 'NOT_REGISTERED',
                'message': 'This RFID card is not registered.'
            })

        user_name = users[rfid]['name']
        print(f"✓ RFID registered to: {user_name}")

        print("\n👤 Starting face verification...")
        captured_encoding, error = capture_face()

        if error:
            print(f"❌ Face capture failed: {error}")
            return jsonify({'status': 'FAILED', 'message': error})

        registered_encoding = users[rfid]['face_encoding']
        match, distance = verify_face(captured_encoding, registered_encoding)

        if match:
            print(f"✅ FACE VERIFIED for {user_name}!")

            attendance_record = {
                'rfid': rfid,
                'name': user_name,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'date': datetime.now().strftime('%Y-%m-%d'),
                'time': datetime.now().strftime('%H:%M:%S'),
                'status': 'Present',
                'height': None,
                'weight': None,
                'bmi': None,
                'bmi_category': None
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
            print("="*50 + "\n")
            return jsonify({
                'status': 'FAILED',
                'message': 'Face verification failed.'
            })

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'status': 'ERROR', 'message': f'Server error: {str(e)}'}), 500


@app.route('/submit_height', methods=['POST'])
def submit_height():
    """ESP32 sends HC-SR04 measured height after face verification"""
    try:
        data = request.json
        rfid = data.get('rfid', '').upper().strip()
        height = float(data.get('height', 0))

        print(f"\n📏 Height received — RFID: {rfid}, Height: {height:.1f} cm")

        if rfid not in users:
            print(f"❌ RFID {rfid} not found in users")
            return jsonify({'status': 'ERROR', 'message': 'RFID not found'})

        if height < 100 or height > 220:
            print(f"❌ Invalid height: {height}")
            return jsonify({'status': 'ERROR', 'message': f'Invalid height value: {height:.1f} cm'})

        user_name = users[rfid]['name']

        # Store in pending_bmi — weight will be entered manually on dashboard
        pending_bmi[rfid] = {
            'name': user_name,
            'height': round(height, 1),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        print(f"✓ Stored pending BMI for {user_name}: height={height:.1f}cm")
        print(f"  Current pending_bmi keys: {list(pending_bmi.keys())}")

        return jsonify({
            'status': 'OK',
            'message': f'Height {height:.1f}cm stored for {user_name}. Enter weight on dashboard.'
        })

    except Exception as e:
        print(f"❌ Error in submit_height: {str(e)}")
        return jsonify({'status': 'ERROR', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# ROUTES — BMI API
# ─────────────────────────────────────────────────────────────

@app.route('/api/pending_bmi')
def get_pending_bmi():
    """Dashboard polls this to show who needs weight entry"""
    result = [{'rfid': k, **v} for k, v in pending_bmi.items()]
    print(f"  [pending_bmi poll] {len(result)} entries: {[r['name'] for r in result]}")
    return jsonify(result)


@app.route('/api/submit_weight', methods=['POST'])
def submit_weight():
    """Dashboard submits weight → server calculates BMI and saves to attendance record"""
    try:
        data = request.json
        rfid = data.get('rfid', '').upper().strip()
        weight = float(data.get('weight', 0))

        print(f"\n⚖️  Weight submission — RFID: '{rfid}', Weight: {weight} kg")
        print(f"   Current pending_bmi keys: {list(pending_bmi.keys())}")

        if rfid not in pending_bmi:
            msg = f'No pending height data for RFID "{rfid}". Please scan card first.'
            print(f"❌ {msg}")
            return jsonify({'status': 'ERROR', 'message': msg})

        if weight < 20 or weight > 300:
            return jsonify({'status': 'ERROR', 'message': 'Invalid weight (must be 20–300 kg)'})

        pending = pending_bmi[rfid]
        height_m = pending['height'] / 100.0
        bmi = round(weight / (height_m ** 2), 1)

        # BMI category
        if bmi < 18.5:
            category = 'Underweight'
        elif bmi < 25.0:
            category = 'Normal'
        elif bmi < 30.0:
            category = 'Overweight'
        else:
            category = 'Obese'

        # Find today's attendance record for this RFID and update it
        today = datetime.now().strftime('%Y-%m-%d')
        updated = False
        for record in reversed(attendance_records):
            if record['rfid'] == rfid and record['date'] == today:
                record['height'] = pending['height']
                record['weight'] = round(weight, 1)
                record['bmi'] = bmi
                record['bmi_category'] = category
                updated = True
                print(f"✓ Updated existing attendance record for {pending['name']}")
                break

        if not updated:
            # No attendance record found today — create a standalone BMI entry
            attendance_records.append({
                'rfid': rfid,
                'name': pending['name'],
                'timestamp': pending['timestamp'],
                'date': today,
                'time': pending['timestamp'].split(' ')[1],
                'status': 'BMI Only',
                'height': pending['height'],
                'weight': round(weight, 1),
                'bmi': bmi,
                'bmi_category': category
            })
            print(f"✓ Created standalone BMI record for {pending['name']}")

        save_attendance()

        # Remove from pending
        del pending_bmi[rfid]

        print(f"✅ BMI for {pending['name']}: {bmi} kg/m² ({category})")

        return jsonify({
            'status': 'OK',
            'name': pending['name'],
            'height': pending['height'],
            'weight': round(weight, 1),
            'bmi': bmi,
            'bmi_category': category
        })

    except Exception as e:
        print(f"❌ Error in submit_weight: {str(e)}")
        return jsonify({'status': 'ERROR', 'message': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────

@app.route('/health')
def health():
    return jsonify({
        'status': 'OK',
        'users': len(users),
        'attendance': len(attendance_records),
        'pending_bmi': len(pending_bmi)
    })


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  SMART ATTENDANCE SYSTEM - SERVER")
    print("="*60)

    load_data()

    print("\n📋 Server Configuration:")
    print(f"   Host: 0.0.0.0")
    print(f"   Port: 5000")
    print(f"   Registered Users: {len(users)}")
    print(f"   Attendance Records: {len(attendance_records)}")

    print("\n🌐 Access Points:")
    print("   Dashboard:    http://localhost:5000")
    print("   API Stats:    http://localhost:5000/api/stats")
    print("   Health Check: http://localhost:5000/health")

    print("\n⚠️  IMPORTANT:")
    print("   1. Make sure your webcam is connected")
    print("   2. Update ESP32 with this computer's IP address")
    print("   3. Register users first: python register.py")

    print("\n" + "="*60)
    print("🚀 Starting server...")
    print("="*60 + "\n")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)