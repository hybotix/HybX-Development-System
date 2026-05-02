# Arduino Portenta X8 — HybX Port Research
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Overview

The Arduino Portenta X8 shares the same fundamental dual-processor architecture as the Arduino UNO Q — Linux MPU + Arduino MCU on the same board, communicating via RPC. HybX was designed around exactly this architecture. A Portenta X8 port is a natural evolution.

The X8 is also the target of Arduino's subscription-based Foundries.io ecosystem. HybX can break that dependency, making the X8 what it should be — a professional dual-processor development platform with no artificial limitations.

---

## Hardware (Official — from Datasheet ABX00049, rev 29/01/2026)

### MPU — NXP i.MX 8M Mini (MIMX8MM6CVTKZAA)
| Property | Value |
|----------|-------|
| CPU | 4x ARM Cortex-A53 @ up to 1.8GHz per core |
| Additional core | 1x ARM Cortex-M4 @ up to 400MHz (**reserved for future use**) |
| L1 Cache (A53) | 32KB instruction + 32KB data per core |
| L2 Cache (A53) | 512KB |
| GPU | 3D (1x shader, OpenGL ES 2.0) + 2D |
| RAM | 2GB LPDDR4 (NT6AN512T32AV) |
| Storage | 16GB eMMC (FEMDRW016G Foresee) |
| OS | Linux (Yocto-based) |
| WiFi | 802.11b/g/n up to 65Mbps (Murata LBEE5KL1DX-883) |
| Bluetooth | 5.1 BR/EDR/LE |
| Ethernet | Gigabit (KSZ9031RNXIA) |
| Security | NXP SE050C2 crypto element (CC EAL 6+), PSA certified |
| Video decode | 1080p60 VP9, H.265, H.264, VP8 |
| Video encode | 1080p60 H.264, VP8 |

### MCU — STMicroelectronics STM32H747AII6 (U20)
| Property | Value |
|----------|-------|
| M7 core | ARM Cortex-M7 @ up to 480MHz, double-precision FPU, 16KB I + 16KB D L1 cache |
| M4 core | ARM Cortex-M4 @ up to 240MHz, FPU, ART Accelerator |
| Flash | 2MB (read-while-write support) |
| RAM | 1MB |
| M7 role | Runs Arduino custom firmware — maps all peripherals as Linux devices. **Invisible to user.** |
| M4 role | Runs user Arduino sketches. Real-time control of motors and time-critical hardware. |

### Core Count — Official
| Processor | Cores |
|-----------|-------|
| i.MX 8M Mini — Cortex-A53 | 4 |
| i.MX 8M Mini — Cortex-M4 (reserved) | 1 |
| STM32H747 — Cortex-M7 (Arduino firmware) | 1 |
| STM32H747 — Cortex-M4 (user sketches) | 1 |
| **Total** | **7** |

**Note on "9 cores" marketing claim:** Arduino's marketing materials claim 9 cores but the official datasheet accounts for only 7. The discrepancy is unresolved — possibly counting GPU shader cores or internal sub-cores. The datasheet is authoritative.

---

## Architecture vs UNO Q

| Aspect | UNO Q | Portenta X8 |
|--------|-------|-------------|
| MPU | Qualcomm QRB2210 (4x Cortex-A53) | NXP i.MX 8M Mini (4x Cortex-A53) |
| MCU | STM32U585 (Cortex-M33) | STM32H747 (Cortex-M7 + M4) |
| Linux OS | Debian | Yocto-based |
| Bridge protocol | msgpack-RPC over Unix socket | msgpackrpc over serial (M4 proxy) |
| Bridge library (MCU) | Arduino_RouterBridge | Arduino_ExtendedBridge / RPC |
| Sketch target | M33 | M4 core |
| M7 role | N/A | Runs Arduino custom firmware as Linux I/O expander |
| Subscription required | No | Optional (Foundries.io) — basic use is free |
| Container architecture | Docker (v2.0, removed in v2.1) | Docker (built-in, Yocto-based) |

---

## Linux-to-MCU Bridge Protocol

This is the **critical difference** from the UNO Q.

### UNO Q
- Protocol: Standard msgpack-RPC
- Transport: Unix socket at `/var/run/arduino-router.sock`
- World-readable, always running
- `hybx_app.py` connects directly — no intermediary

### Portenta X8
- Protocol: msgpackrpc
- Transport: Serial port between i.MX8 and STM32H747
- Runs via `py-serialrpc` — a Python service that bridges serial to RPC
- `py-serialrpc` is typically run in a Docker container
- The M4 core runs the user sketch; the M7 runs Arduino's firmware as an I/O proxy

**Key challenge:** The RPC communication between Linux and the M4 core is notoriously unreliable on recent X8 firmware. Multiple forum reports confirm the official tutorial is broken on firmware v861+. This is a significant known issue that must be resolved before HybX can target the X8.

### What HybX needs to do differently
On the UNO Q, `hybx_app.py` connects directly to the Unix socket. On the X8, it would need to either:
1. Connect via `py-serialrpc` (replicating the existing broken approach), or
2. Implement a direct serial RPC connection to the STM32H747, bypassing `py-serialrpc`

Option 2 is the HybX way — understand the protocol at the wire level (same approach used to reverse-engineer the UNO Q router socket) and implement it directly in `hybx_app.py`.

---

## Subscription vs Free Use

The Foundries.io subscription is **not required** for basic use. From Arduino's own documentation:

> "The user has full control of the containers that the board is executing, having the option of creating and running custom containers on its own without the requirement of any additional subscription services and totally free of charge."

The subscription adds:
- OTA update management for Linux distribution
- Fleet management (multi-device)
- Enterprise security maintenance

None of these are needed for single-board development. HybX can operate entirely without the subscription.

---

## HybX Port Requirements

### What carries over unchanged
- `hybx_config` — board-agnostic already
- `project`, `board`, `update` — board-agnostic
- Versioning system, venv, symlink pattern
- All app Python code using `Bridge.call()` / `Bridge.provide()` pattern

### What needs new work

**1. Board definition — `boards/portenta-x8.json`**
- New toolchain paths (mbed OS / arm-none-eabi for STM32H747)
- New compile flags for Cortex-M7/M4
- New linker scripts
- New flash configuration

**2. Bridge protocol — `hybx_app.py` update**
- X8 uses serial-based msgpackrpc, not a Unix socket
- Need to probe the actual wire protocol (same approach as UNO Q prober.py)
- New `_Bridge` implementation targeting the X8's serial RPC

**3. Compiler — `HybXCompiler` update**
- New board definition for STM32H747 M4 core target
- mbed OS instead of Zephyr
- Different library search paths
- Different core compilation

**4. Flasher — `HybXFlasher` update**
- STM32H747 uses different flash mechanism than STM32U585
- May use USB DFU or JLink/OpenOCD via SWD

**5. `hybx_vl53l5cx` platform layer**
- New platform.cpp using Wire (mbed OS) instead of Zephyr native I2C
- STM32H747 at 480MHz should handle firmware upload without DMA tricks

---

## Known Issues to Investigate

- **RPC broken on recent firmware** — Multiple reports of `py-serialrpc` failing on firmware v861+. Root cause unknown. Must be resolved before HybX can target X8.
- **M7 vs M4 role** — The M7 runs Arduino's proprietary firmware as an I/O proxy. The user's sketch runs on the M4. This is different from the UNO Q where the MCU is a single core running the user's sketch.
- **Serial port path** — Need to determine exact serial device path on X8 Linux side for the RPC bridge.
- **Docker dependency** — `py-serialrpc` currently runs in Docker. HybX would eliminate this.

---

## Research Status

| Topic | Status |
|-------|--------|
| Hardware architecture | ✅ Documented |
| Bridge protocol type | ✅ Known (msgpackrpc over serial) |
| Bridge wire protocol details | 🔲 Needs probing (same approach as UNO Q) |
| RPC reliability issues | ⚠️ Known broken on recent firmware — root cause unknown |
| MCU toolchain | 🔲 Needs investigation (mbed OS vs Zephyr) |
| Flash mechanism | 🔲 Needs investigation |
| Subscription bypass | ✅ Confirmed not required |

---

## Next Steps

1. Get X8 connected and running
2. Probe the serial RPC protocol at the wire level
3. Determine if recent firmware RPC issues can be bypassed
4. Implement X8 platform layer in `hybx_app.py`
5. Add `boards/portenta-x8.json` board definition
6. Test `HybXCompiler` and `HybXFlasher` against STM32H747 M4

---

*Hybrid RobotiX — San Diego, CA*
