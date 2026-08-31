# 3D Models — A.W.A.K.E. 2.0

This folder contains STL files for 3D-printed parts used in the A.W.A.K.E. 2.0 drowsiness detection system.

## Model: Super Ultra Compact Pan-Tilt Camera Mount v1

Source: [Cults3D — ZalophusDokdo](https://cults3d.com/en/3d-model/gadget/super-ultra-compact-pan-tilt-camera-mount-v1)

### STL Files

```
super-ultra-compact-pan-tilt-camera-mount-v1/
├── PanTiltbase_RPi_r01.stl          # Pan/tilt base bracket
├── cameraMount_RPi_r01.stl          # Camera mount (standard)
├── cameraMount_RPi_R_r01.stl        # Camera mount (reversed)
├── cameraMount_r01.stl              # Generic camera mount
├── cameraCover_RPi_r01.stl          # Camera cover/shield
├── vertMount_RPi_r01.stl            # Vertical mount for Pi
└── vertMount_Cover_RPi_r01.stl      # Vertical mount cover
```

### Printing Notes

- **Material:** PLA or PETG recommended
- **Layer height:** 0.2 mm
- **Infill:** 20–30% for structural parts, 100% for servo mounts
- **Supports:** Enable for overhangs > 45°
- **Designed for:** Raspberry Pi Camera v2 + MG90S servos

---

## Model: LM2596 Buck Converter Enclosure

Source: [Thingiverse — Estep](https://www.thingiverse.com/thing:4096861)

### Description

A 3D-printed enclosure for the LM2596S buck converter. Allows voltage measurement and adjustment without removing the cover. Two versions are available: one for cables soldered with wires exiting the sides, and one for cables exiting the back. Requires 2 screws for mounting (4 screws if you want a removable top).

### STL Files

```
LM2596 Buck Converter Enclosure - 4096861/
├── Buttom.STL                      # Bottom (version 1: cables exiting sides)
├── Buttom-02.STL                   # Bottom (version 2: cables exiting back)
├── Top.STL                         # Top (version 1)
└── Top-02.STL                      # Top (version 2)
```

### Printing Notes

- **Material:** PLA or PETG recommended
- **Layer height:** 0.2 mm
- **Infill:** 20–30%
- **Designed for:** LM2596S buck converter module
