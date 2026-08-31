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

# ── Check lgpio error text ──────────────────────────────────
print("\n=== lgpio error text samples ===")
for code in range(-20, 1):
    txt = lgpio.error_text(code)
    if txt != "unknown error":
        print(f"  error_text({code}) = '{txt}'")

# ── Test 1: tx_servo with wide range ────────────────────────
print("\n=== Test 1: tx_servo ===")
test_pulses = [1000, 1100, 1200, 1300, 1500, 1700, 1800, 1900, 2000]
for pulse in test_pulses:
    ret = lgpio.tx_servo(chip, PIN, pulse)
    err_text = lgpio.error_text(ret) if ret < 0 else "OK"
    print(f"  tx_servo({pulse}us) ret={ret} ({err_text})")
    time.sleep(0.3)

# Stop
lgpio.tx_servo(chip, PIN, 0)
print("  (stopped)")

# ── Test 2: raw gpio_write toggle (manual PWM) ──────────────
print("\n=== Test 2: gpio_write toggle (manual PWM) ===")
print("  Toggling GPIO 12 at ~50Hz for 3 seconds...")
print("  (If servo hums/buzzes, the pin works)")

start = time.time()
cycles = 0
while time.time() - start < 3.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.001)   # 1ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.019)   # 19ms LOW  (total ~20ms = 50Hz)
    cycles += 1

lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {cycles} cycles in 3s (50Hz)")

# ── Test 3: gpio_write at 1500us pulse width ────────────────
print("\n=== Test 3: gpio_write 50Hz, 1500us pulse (neutral) ===")
start = time.time()
cycles = 0
while time.time() - start < 2.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0015)   # 1.5ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0185)   # 18.5ms LOW
    cycles += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {cycles} cycles (should stop servo)")

# ── Test 4: gpio_write at 1100us (spin one direction) ──────
print("\n=== Test 4: gpio_write 50Hz, 1100us pulse (spin fast) ===")
start = time.time()
cycles = 0
while time.time() - start < 3.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0011)   # 1.1ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0189)   # 18.9ms LOW
    cycles += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {cycles} cycles (should spin)")

# ── Test 5: gpio_write at 1900us (spin other direction) ────
print("\n=== Test 5: gpio_write 50Hz, 1900us pulse (spin opposite) ===")
start = time.time()
cycles = 0
while time.time() - start < 3.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0019)   # 1.9ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0181)   # 18.1ms LOW
    cycles += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {cycles} cycles (should spin opposite)")

# Cleanup
lgpio.gpio_free(chip, PIN)
lgpio.gpiochip_close(chip)
print("\nDone. Which test made the servo move?")
