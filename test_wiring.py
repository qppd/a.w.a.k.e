#!/usr/bin/env python3
"""Quick wiring test — verify GPIO 12 signal reaches the servo.

This test:
1. Blinks GPIO 12 at 1Hz (toggle every 0.5s)
   → If LED on GPIO 12 blinks, pin is alive
2. Sends 1100µs pulse via gpio_write for 3 seconds
   → If servo spins, wiring is good
3. Sends 1900µs pulse via gpio_write for 3 seconds
   → If servo spins opposite, wiring is good

If none of these produce any servo response, the issue is:
- GPIO 12 not connected to servo signal wire
- Servo not getting power (5V)
- Broken servo

Usage: sudo python test_wiring.py
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

ret = lgpio.gpio_claim_output(chip, PIN)
print(f"GPIO {PIN} claimed: ret={ret}")

# ── Test 1: Simple blink (1Hz) ──────────────────────────────
print("\n=== Test 1: Blink GPIO 12 at 1Hz (5 seconds) ===")
print("  Watch for an LED on GPIO 12, or use multimeter")
for i in range(5):
    lgpio.gpio_write(chip, PIN, 1)
    print(f"  HIGH  ({i+1}/5)")
    time.sleep(0.5)
    lgpio.gpio_write(chip, PIN, 0)
    print(f"  LOW   ({i+1}/5)")
    time.sleep(0.5)

# ── Test 2: Servo pulse 1100µs (spin direction 1) ───────────
print("\n=== Test 2: 1100µs pulse for 5 seconds ===")
print("  Watch if pan servo spins in ONE direction")
start = time.time()
count = 0
while time.time() - start < 5.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0011)   # 1.1ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0189)   # 18.9ms LOW (total ~20ms = 50Hz)
    count += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {count} pulses sent")

# ── Test 3: Servo pulse 1900µs (spin direction 2) ───────────
print("\n=== Test 3: 1900µs pulse for 5 seconds ===")
print("  Watch if pan servo spins in OPPOSITE direction")
start = time.time()
count = 0
while time.time() - start < 5.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0019)   # 1.9ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0181)   # 18.1ms LOW
    count += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {count} pulses sent")

# ── Test 4: Neutral pulse 1500µs (should stop) ──────────────
print("\n=== Test 4: 1500µs pulse for 3 seconds (should stop) ===")
start = time.time()
count = 0
while time.time() - start < 3.0:
    lgpio.gpio_write(chip, PIN, 1)
    time.sleep(0.0015)   # 1.5ms HIGH
    lgpio.gpio_write(chip, PIN, 0)
    time.sleep(0.0185)   # 18.5ms LOW
    count += 1
lgpio.gpio_write(chip, PIN, 0)
print(f"  Done — {count} pulses sent")

# Cleanup
lgpio.gpio_free(chip, PIN)
lgpio.gpiochip_close(chip)

print("\n" + "=" * 50)
print("RESULTS:")
print("  - If LED blinks in Test 1: GPIO 12 pin is alive")
print("  - If servo spins in Test 2/3: Servo + wiring OK")
print("  - If NO response at all:")
print("    → Check GPIO 12 wire to servo signal pin")
print("    → Check servo has 5V power")
print("    → Try servo on GPIO 13 (known working pin)")
print("    → Try a different servo on GPIO 12")
print("=" * 50)
