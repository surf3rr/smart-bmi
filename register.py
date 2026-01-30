"""
User Registration Script
Register RFID cards with face recognition data
"""

import cv2
import face_recognition
import numpy as np
import json
import os
from datetime import datetime

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")

os.makedirs(DATA_DIR, exist_ok=True)

def load_users():
    """Load existing users"""
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            data = json.load(f)
            users = {}
            for rfid, user_data in data.items():
                users[rfid] = {
                    'name': user_data['name'],
                    'face_encoding': np.array(user_data['face_encoding'])
                }
            return users
    return {}

def save_users(users):
    """Save users to file"""
    data = {}
    for rfid, user_data in users.items():
        data[rfid] = {
            'name': user_data['name'],
            'face_encoding': user_data['face_encoding'].tolist()
        }
    with open(USERS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def capture_face_with_preview():
    """Capture face with live preview"""
    print("\n📷 Opening camera...")
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        print("❌ Could not open camera!")
        return None
    
    print("\n" + "="*60)
    print("  FACE CAPTURE INSTRUCTIONS")
    print("="*60)
    print("  - Look directly at the camera")
    print("  - Ensure good lighting")
    print("  - Remove glasses if possible")
    print("  - Keep a neutral expression")
    print("  - Press SPACE when ready")
    print("  - Press ESC to cancel")
    print("="*60 + "\n")
    
    face_encoding = None
    
    while True:
        ret, frame = camera.read()
        
        if not ret:
            print("❌ Failed to grab frame")
            break
        
        # Convert to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Find faces
        face_locations = face_recognition.face_locations(rgb_frame)
        
        # Draw rectangles around faces
        display_frame = frame.copy()
        for (top, right, bottom, left) in face_locations:
            cv2.rectangle(display_frame, (left, top), (right, bottom), (0, 255, 0), 2)
        
        # Add text
        if len(face_locations) == 0:
            cv2.putText(display_frame, "No face detected", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        elif len(face_locations) == 1:
            cv2.putText(display_frame, "Face detected! Press SPACE", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, "Multiple faces! Only one person", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        cv2.imshow('Face Registration - Press SPACE to capture', display_frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # Press SPACE to capture
        if key == ord(' '):
            if len(face_locations) == 1:
                print("\n✓ Capturing face...")
                face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                if len(face_encodings) > 0:
                    face_encoding = face_encodings[0]
                    print("✓ Face captured successfully!")
                    break
                else:
                    print("❌ Failed to encode face. Try again.")
            elif len(face_locations) == 0:
                print("❌ No face detected. Please face the camera.")
            else:
                print("❌ Multiple faces detected. Only one person at a time.")
        
        # Press ESC to cancel
        elif key == 27:
            print("\n❌ Cancelled by user")
            break
    
    camera.release()
    cv2.destroyAllWindows()
    
    return face_encoding

def register_user():
    """Register a new user"""
    users = load_users()
    
    print("\n" + "="*60)
    print("  USER REGISTRATION")
    print("="*60)
    
    # Get user name
    name = input("\nEnter user name: ").strip()
    if not name:
        print("❌ Name cannot be empty!")
        return
    
    # Get RFID
    print("\n📇 Now scan the RFID card...")
    print("   (The UID will appear in the ESP32 serial monitor)")
    rfid = input("Enter RFID UID (from ESP32): ").strip().upper()
    
    if not rfid:
        print("❌ RFID cannot be empty!")
        return
    
    # Check if RFID already exists
    if rfid in users:
        print(f"\n⚠️  RFID {rfid} is already registered to: {users[rfid]['name']}")
        overwrite = input("Do you want to overwrite? (yes/no): ").strip().lower()
        if overwrite != 'yes':
            print("❌ Registration cancelled")
            return
    
    # Capture face
    print(f"\n👤 Capturing face for: {name}")
    face_encoding = capture_face_with_preview()
    
    if face_encoding is None:
        print("❌ Face capture failed. Registration cancelled.")
        return
    
    # Save user
    users[rfid] = {
        'name': name,
        'face_encoding': face_encoding
    }
    
    save_users(users)
    
    print("\n" + "="*60)
    print("  ✅ REGISTRATION SUCCESSFUL!")
    print("="*60)
    print(f"   Name: {name}")
    print(f"   RFID: {rfid}")
    print(f"   Total Users: {len(users)}")
    print("="*60 + "\n")

def list_users():
    """List all registered users"""
    users = load_users()
    
    print("\n" + "="*60)
    print("  REGISTERED USERS")
    print("="*60)
    
    if not users:
        print("  No users registered yet.")
    else:
        for i, (rfid, data) in enumerate(users.items(), 1):
            print(f"  {i}. {data['name']}")
            print(f"     RFID: {rfid}")
            print()
    
    print(f"Total Users: {len(users)}")
    print("="*60 + "\n")

def delete_user():
    """Delete a registered user"""
    users = load_users()
    
    if not users:
        print("\n❌ No users to delete!")
        return
    
    list_users()
    
    rfid = input("Enter RFID to delete: ").strip().upper()
    
    if rfid not in users:
        print(f"❌ RFID {rfid} not found!")
        return
    
    name = users[rfid]['name']
    confirm = input(f"Delete {name} ({rfid})? (yes/no): ").strip().lower()
    
    if confirm == 'yes':
        del users[rfid]
        save_users(users)
        print(f"✓ Deleted {name}")
    else:
        print("❌ Deletion cancelled")

def main():
    """Main menu"""
    while True:
        print("\n" + "="*60)
        print("  SMART ATTENDANCE - USER REGISTRATION")
        print("="*60)
        print("  1. Register new user")
        print("  2. List all users")
        print("  3. Delete user")
        print("  4. Exit")
        print("="*60)
        
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == '1':
            register_user()
        elif choice == '2':
            list_users()
        elif choice == '3':
            delete_user()
        elif choice == '4':
            print("\n👋 Goodbye!\n")
            break
        else:
            print("❌ Invalid choice!")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  SMART ATTENDANCE SYSTEM")
    print("  User Registration Tool")
    print("="*60)
    print("\n⚠️  Make sure:")
    print("   1. Webcam is connected")
    print("   2. ESP32 is running (to get RFID UIDs)")
    print("   3. Good lighting for face capture")
    
    main()
