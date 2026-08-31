#!/usr/bin/env python3
"""Quick test — find the correct pulse range for the 360° pan servo.

Tests different pulse widths to find:
1. The neutral point (where servo stops)
2. The minimum pulse to start spinning
3. Both spin directions

Usage: sudo python test_pan.py
"""
import sys
import time

try:
    from rpi_hardware_pwm import HardwarePWM
except ImportError:
    print("ERROR: pip install rpi-hardware-pwm")
    sys.exit(1)

PWM_FREQ = 50
PWM_PERIOD_US = 1_000_000 // PWM_FREQ  # 20000µs

def us_to_duty(pulse_us):
    return pulse_us / PWM_PERIOD_US * 100.0

pwm = HardwarePWM(pwm_channel=0, hz=PWM_FREQ, chip=0)

print("=== Pan Servo Pulse Test (GPIO 12) ===\n")

# Test 1: Start at neutral
print("--- Test 1: Neutral (1500us) ---")
pwm.start(us_to_duty(1500))
print(f"  1500us = {us_to_duty(1500):.2f}% duty")
print("  Servo should be STOPPED. Press Enter to continue...")
input()

# Test 2: Sweep low to high
test_pulses = [500, 750, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2250, 2500]
for pulse in test_pulses:
    duty = us_to_duty(pulse)
    pwm.change_duty_cycle(duty)
    print(f"  {pulse}us = {duty:.2f}% duty — watch servo (3s)")
    time.sleep(3)

# Stop
pwm.change_duty_cycle(us_to_duty(1500))
print("\n  Back to neutral (1500us)")
time.sleep(1)
pwm.stop()

print("\n=== Done ===")
print("Note which pulse values made the servo spin and in which direction.")
print("The neutral point is where the servo stops spinning.")
