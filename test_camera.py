"""
Camera Test Script
Quickly test if your webcam is working
"""

import cv2
import sys

print("\n" + "="*60)
print("  CAMERA TEST")
print("="*60)

print("\n📷 Attempting to open camera...")

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("❌ ERROR: Could not open camera!")
    print("\nPossible solutions:")
    print("  1. Check if camera is connected")
    print("  2. Check if another app is using the camera")
    print("  3. Try installing: pip install opencv-python")
    print("  4. On Linux, install: sudo apt-get install v4l-utils")
    sys.exit(1)

print("✓ Camera opened successfully!")
print("\n" + "="*60)
print("  Press 'q' to quit")
print("  Press 's' to save a test image")
print("="*60 + "\n")

frame_count = 0

while True:
    ret, frame = camera.read()
    
    if not ret:
        print("❌ Failed to grab frame")
        break
    
    frame_count += 1
    
    # Add text overlay
    cv2.putText(frame, f"Frame: {frame_count}", (10, 30),
               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(frame, "Press 'q' to quit, 's' to save", (10, 70),
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Display
    cv2.imshow('Camera Test', frame)
    
    # Check for key press
    key = cv2.waitKey(1) & 0xFF
    
    if key == ord('q'):
        print("\n✓ Test completed successfully!")
        break
    elif key == ord('s'):
        filename = f"test_image_{frame_count}.jpg"
        cv2.imwrite(filename, frame)
        print(f"✓ Saved: {filename}")

camera.release()
cv2.destroyAllWindows()

print("\n" + "="*60)
print("  Camera test finished!")
print("="*60 + "\n")
