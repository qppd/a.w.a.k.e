#!/usr/bin/env python3
"""Minimal test — check if GPIO 12 can drive the 360° continuous servo.

Tests multiple pulse widths to find the deadband.
If tx_servo doesn't work, falls back to raw gpio_write toggling.

Usage: sudo python test_pwm.py
"""
import sys
import time

if "/usr/lib/python3/dist-packages" not in sys.path:
    sys.path.insert(0, "/usr/lib/python3/dist-packages")

try:
    import lgpio
except ImportError:
    print("ERROR: pip install lgpio")
    sys.exit(1)

PIN = 12

try:
    chip = lgpio.gpiochip_open(0)
except lgpio.error as exc:
    print(f"ERROR: {exc}")
    sys.exit(1)

print(f"Chip opened: {chip}")

ret = lgpio.gpio_claim_output(chip, PIN)
print(f"Claim GPIO {PIN}: ret={ret}")

mode = lgpio.gpio_get_mode(chip, PIN)
print(f"Mode after claim: {mode}")

# ── Test 1: tx_servo with wide range ────────────────────────
print("\n=== Test 1: tx_servo ===")
test_pulses = [1000, 1100, 1200, 1300, 1500, 1700, 1800, 1900, 2000]
for pulse in test_pulses:
    ret = lgpio.tx_servo(chip, PIN, pulse)
    print(f"  tx_servo({pulse}us) ret={ret}", end="")
    # Check if pin is actually toggling
    time.sleep(0.3)

# Stop
lgpio.tx_servo(chip, PIN, 0)
print("\n  (stopped)")

# ── Test 2: raw gpio_write toggle (1kHz square wave) ────────
print("\n=== Test 2: gpio_write toggle (manual PWM) ===")
print("  Toggling GPIO 12 at ~1kHz for 3 seconds...")
print("  (If servo hums/buzzes, the pin works)")

start = time.time()
cycles = 0
while time.time() - start < 3.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0005)   # 0.5ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0005)   # 0.5ms LOW
    cycles += 1

lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {cycles} cycles in 3s")

# ── Test 3: tx_pwm (continuous PWM) ─────────────────────────
print("\n=== Test 3: tx_pwm (50Hz, 7.5% duty = 1500us equivalent) ===")
ret = lgpio.tx_pwm(chip, PIN, 50, 75000)  # 75000/1_000_000 = 7.5%
print(f"  tx_pwm(50Hz, 75000) ret={ret}")
time.sleep(2)
lgpio.tx_pwm(chip, PIN, 50, 0)  # stop
print("  (stopped)")

print("\n=== Test 4: tx_pwm (50Hz, 5% duty = 1000us) ===")
ret = lgpio.tx_pwm(chip, PIN, 50, 50000)  # 5%
print(f"  tx_pwm(50Hz, 50000) ret={ret}")
time.sleep(2)
lgpio.tx_pwm(chip, PIN, 50, 0)
print("  (stopped)")

print("\n=== Test 5: tx_pwm (50Hz, 10% duty = 2000us) ===")
ret = lgpio.tx_pwm(chip, PIN, 50, 100000)  # 10%
print(f"  tx_pwm(50Hz, 100000) ret={ret}")
time.sleep(2)
lgpio.tx_pwm(chip, PIN, 50, 0)
print("  (stopped)")

# Cleanup
lgpio.gpio_free(chip, PIN)
lgpio.gpiochip_close(chip)
print("\nDone. Which test made the servo move?")
