# HybX Board Support
## Hybrid RobotiX

This document describes all boards that are supported, in development,
or on the radar for future HybX Development System support.

---

## Status Definitions

| Status | Meaning |
|--------|---------|
| **Supported** | Fully integrated, tested, and documented |
| **In Development** | Active work underway, not yet stable |
| **On Radar** | Planned or under research, no active development yet |

---

## Supported Boards

### Arduino UNO Q

| Property | Value |
|----------|-------|
| Status | Supported |
| Manufacturer | Arduino / Qualcomm |
| FQBN | `arduino:zephyr:unoq` |
| MPU | Qualcomm Dragonwing QRB2210 (quad-core Arm Cortex-A53, up to 2 GHz) |
| MCU | STMicroelectronics STM32U585 (Arm Cortex-M33, up to 160 MHz) |
| OS | Debian Linux (MPU) + Zephyr RTOS with Arduino Core (MCU) |
| GPIO Logic | 3.3V |
| RAM | 2 GB or 4 GB LPDDR4X (MPU) / 786 KB SRAM (MCU) |
| Storage | 16 GB or 32 GB eMMC |
| Connectivity | Wi-Fi 5, Bluetooth 5.1 |
| Form Factor | Arduino UNO |
| SSH | Yes (arduino@uno-q.local) |
| App Management | HybX native — plain Python processes, no Docker |

**Architecture:** Dual-processor. The MPU runs Debian Linux and Python apps
as plain Python processes managed by HybX. The MCU runs Arduino sketches on
Zephyr RTOS. The two communicate via the Arduino Bridge (msgpack-RPC over
Unix socket at `/var/run/arduino-router.sock`).

**Key HybX discoveries:**
- QWIIC connector is on `Wire1` (I2C bus 1), not the default `Wire`
- `Wire1.begin()` must be called BEFORE `Bridge.begin()` — reversing this hangs the MCU
- `Bridge.provide()` calls must be in `setup()` after `Bridge.begin()`
- msgpack-RPC wire protocol: `[0, msgid, method, [args]]` request, `[1, msgid, error, result]` response
- `arduino-router.sock` is world-writable and always running — no root needed to connect
- Libraries are stored in `~/.arduino15/internal/` in a nested hash layout
- GPIO pins operate at 3.3V — shields designed for 5V Uno may need level shifting
- VL53L5CX firmware upload requires DMA-enabled I2C (see KNOWN_ISSUES.md)

**Known issues:** See `KNOWN_ISSUES.md`

---

## In Development

### Arduino Portenta X8

| Property | Value |
|----------|-------|
| Status | In Development |
| Manufacturer | Arduino |
| MPU | NXP i.MX 8M Mini (quad-core Arm Cortex-A53) |
| MCU | STMicroelectronics STM32H747 (Arm Cortex-M7 + M4) |
| OS | Linux (Yocto-based) |
| Connectivity | Wi-Fi, Bluetooth, Gigabit Ethernet |
| Form Factor | Portenta |
| Shell Access | adb (confirmed) |
| SSH | Under investigation |
| App Management | Under investigation — Arduino subscription dependency being researched |

**Notes:** Arduino ties the X8 to a subscription service for full functionality.
HybX development is focused on breaking that dependency and establishing a
fully independent workflow. Research ongoing.

---

## On Radar

### Espressif ESP32-H2

| Property | Value |
|----------|-------|
| Status | On Radar |
| Manufacturer | Espressif |
| MCU | 32-bit RISC-V, up to 96 MHz |
| Connectivity | IEEE 802.15.4 (Thread 1.x, Zigbee 3.x), Bluetooth 5 LE, Bluetooth Mesh |
| No WiFi | Pairs with ESP32-C6 for WiFi/Thread border router architecture |
| SDK | ESP-IDF |
| Certifications | Thread Interoperability Certificate, Zigbee-Compliant Platform |

**Notes:** Purpose-built for low-power mesh networking. Primary interest is
OpenThread — vendor-neutral, open-source Thread protocol stack. Candidate
for distributed sensor nodes reporting over a Thread mesh. Pairs with
ESP32-C6 as a Thread Border Router bridging to WiFi/MQTT infrastructure.

### Espressif ESP32-C6

| Property | Value |
|----------|-------|
| Status | On Radar |
| Manufacturer | Espressif |
| MCU | 32-bit RISC-V, up to 160 MHz |
| Connectivity | Wi-Fi 6, Bluetooth 5 LE, IEEE 802.15.4 (Thread, Zigbee) |
| SDK | ESP-IDF |

**Notes:** Natural pairing with the ESP32-H2. Handles the WiFi side of a
Thread Border Router while the H2 handles the mesh radio. Both chips share
the same ESP-IDF SDK making a split-radio architecture straightforward.

---

## Adding a New Board

To add a board to HybX:

1. Add a board type definition: `board type add <n>`
2. Add project type definitions: `project type add <n>`
3. Document the board in this file
4. Add any board-specific discoveries to `KNOWN_ISSUES.md`
5. Open a pull request

See `CONTRIBUTING.md` for standards and `docs/GETTING_STARTED.md` for
the full setup workflow.

---

*Hybrid RobotiX — San Diego, CA*
