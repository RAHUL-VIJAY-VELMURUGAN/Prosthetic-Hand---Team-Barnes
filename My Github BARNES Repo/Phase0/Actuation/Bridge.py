#!/usr/bin/env python
#
# ********* Gen Write Example      *********

import sys
import os
import time

if os.name == 'nt':
    import msvcrt
    def getch():
        return msvcrt.getch().decode()
else:
    import sys, tty, termios
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    def getch():
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

sys.path.append("..")
from STservo_sdk import * # ===============================
# DRIVER CONFIG
# ===============================
DEVICENAME = '/dev/ttyACM0'   # Waveshare driver port
BAUDRATE = 1000000

# ===============================
# SERVO IDS
# ===============================
THUMB_ID = 1
INDEX_MIDDLE_ID = 3
RING_PINKY_ID = 5

SERVO_IDS = [THUMB_ID, INDEX_MIDDLE_ID, RING_PINKY_ID]

# ===============================
# POSITION CONFIG
# ===============================
REST_POS = 2048
CLOSE_DELTA = 1600
PINCH_DELTA = 1000

MIN_POS = 0
MAX_POS = 4095

MOVING_SPEED = 2400
MOVING_ACC = 50

# ===============================
# STATE TRACKING
# ===============================
current_state = -1 # Set to -1 so intent 0 works on the very first input

# ===============================
# INIT DRIVER
# ===============================
portHandler = PortHandler(DEVICENAME)
packetHandler = sts(portHandler)

if not portHandler.openPort():
    print("Failed to open servo port")
    quit()

if not portHandler.setBaudRate(BAUDRATE):
    print("Failed to set baudrate")
    quit()

print("Servo driver ready")

# ===============================
# HELPER FUNCTIONS
# ===============================
def clamp_position(pos):
    return max(MIN_POS, min(MAX_POS, pos))

def move_servo(servo_id, position):
    position = clamp_position(position)

    # Fire and forget actuation
    result, error = packetHandler.WritePosEx(
        servo_id,
        position,
        MOVING_SPEED,
        MOVING_ACC
    )

    if result != COMM_SUCCESS:
        print(packetHandler.getTxRxResult(result))
    if error != 0:
        print(packetHandler.getRxPacketError(error))

# ===============================
# INTENT HANDLER
# ===============================
def handle_intent(intent):
    global current_state

    if intent == current_state:
        return

    targets = {}

    # -------- REST --------
    if intent == 0:
        targets = {sid: REST_POS for sid in SERVO_IDS}

    # -------- CLOSE --------
    elif intent == 1:
        targets = {
            THUMB_ID: REST_POS + CLOSE_DELTA,
            INDEX_MIDDLE_ID: REST_POS + CLOSE_DELTA,
            RING_PINKY_ID: REST_POS + CLOSE_DELTA
        }

    # -------- PINCH --------
    elif intent == 2:
        targets = {
            THUMB_ID: REST_POS + PINCH_DELTA,
            INDEX_MIDDLE_ID: REST_POS + PINCH_DELTA,
            RING_PINKY_ID: REST_POS
        }

    # Execute all movements immediately
    for sid, target in targets.items():
        move_servo(sid, target)

    current_state = intent
    print(f"Motors commanded to Intent {intent}")

# ===============================
# MAIN LOOP (Keyboard Input)
# ===============================
def main():

    print("\nProsthetic Bridge Running - Open Loop Mode")
    print("0 → REST")
    print("1 → CLOSE")
    print("2 → PINCH")
    print("q → Quit\n")

    while True:
        user_input = input("Enter intent: ")

        if user_input.lower() == 'q':
            break

        try:
            intent = int(user_input)

            if intent in [0, 1, 2]:
                handle_intent(intent)
            else:
                print("Invalid input. Use 0, 1, 2 or q.")

        except ValueError:
            print("Invalid input. Use 0, 1, 2 or q.")

    portHandler.closePort()
    print("Program exited.")

if __name__ == "__main__":
    main()
