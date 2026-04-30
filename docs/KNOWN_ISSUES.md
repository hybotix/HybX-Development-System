# HybX Development System — Known Issues
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Open Issues

---

### ST ToF Sensor Compatibility — HybX Development System v1.x vs v2.0

**Status:** Informational — platform constraint documented

#### Summary

ST FlightSense ToF sensors fall into two categories based on firmware architecture:

**ROM-based sensors** — firmware is built into the sensor hardware. Initialization
only requires I2C register writes (small transactions). **These work on UNO Q v1.x.**

**RAM-based sensors** — sensor contains no persistent firmware. The host must
upload ~86KB of firmware over I2C at every boot as a single continuous transaction.
The Zephyr STM32 I2C driver 500ms kernel timeout cannot accommodate this.
**These require v2.0 DMA support.**

#### Sensor Compatibility Table

| Sensor | Zones | Firmware | Works v1.x | Works v2.0 | Notes |
|--------|-------|----------|-----------|-----------|-------|
| VL53L0X | 1 | ROM | ✅ Yes | ✅ Yes | Basic proximity, legacy |
| VL53L1X | 1 | ROM | ✅ Yes | ✅ Yes | Excellent accuracy, 4m range |
| VL53L4CD | 1 | ROM | ✅ Yes | ✅ Yes | **Recommended for v1.x HSP** |
| VL53L4CX | 1 | ROM | ✅ Yes | ✅ Yes | Superset of L4CD, histogram |
| VL53L5CX | 8×8 | RAM ~86KB | ❌ No | ✅ Yes | Primary HSP target |
| VL53L7CH | 8×8 | RAM ~86KB | ❌ No | ✅ Yes | L5CX successor |
| VL53L8CH | 8×8 | RAM ~86KB | ❌ No | ✅ Yes | Latest generation |

#### Recommendation for v1.x HSP

The **VL53L4CD** ([SparkFun Qwiic breakout](https://www.sparkfun.com/products/18993))
is recommended for HSP proximity sensing under v1.x:
- Single-zone, up to 1.3m range
- ROM-based — no firmware upload required
- Full ULD platform layer (same pattern as hybx_vl53l5cx)
- Available on SparkFun Qwiic — direct QWIIC connection to UNO Q Wire1
- Works with the lsm6dsox Bridge pattern proven on UNO Q

The **VL53L1X** ([SparkFun Qwiic breakout](https://www.sparkfun.com/products/14722))
is also an option for longer range (up to 4m) single-zone proximity.

#### v2.0 Target

Full 8×8 depth map capability via VL53L5CX (or L7CH/L8CH) becomes available
in v2.0 when `CONFIG_I2C_STM32_V2_DMA=y` is enabled in the HybX Build System.
The `hybx_vl53l5cx` library is complete and ready — only the platform I2C
transfer constraint blocks it on v1.x.

---

### VL53L5CX Cannot Initialize on Arduino UNO Q (v1.x Platform Limitation)

**Status:** Open — v1.x platform limitation. Deferred to v2.0 (HybX Build System).
**Affects:** monitor-vl53l5cx, sparkfun-vl53-test, serial-vl53l5cx

#### Problem

The VL53L5CX sensor firmware upload (~85KB over I2C) hangs indefinitely
on the Arduino UNO Q's Wire1 (Zephyr ZephyrI2C). This affects ALL libraries
— both the SparkFun VL53L5CX library and hybx_vl53l5cx exhibit the same hang.

The sensor itself is confirmed good:
- Works correctly with Arduino Nano ESP32
- I2C probe (Wire1.beginTransmission/endTransmission) returns ACK at 0x29
- vl53-diag app confirms sensor presence on Wire1

#### What We Know

- Wire1 on UNO Q is `arduino::ZephyrI2C` backed by Zephyr's `i2c_write()` kernel call
- ZephyrI2C uses a 256-byte ring buffer for TX
- `endTransmission()` sends the entire ring buffer via a single `i2c_write()` call
- Our WrMulti chunks at 32 bytes — well within buffer limits
- The ST ULD `_vl53l5cx_poll_for_answer()` had an infinite loop bug on timeout (fixed)
- The hang occurs during `vl53l5cx_init()` — likely during the firmware upload `WrMulti`
  calls or during one of the poll loops waiting for the sensor to respond

#### Root Cause

The ST ULD requires single I2C transactions of up to 32,800 bytes write
(UM2887, Table 2). The VL53L5CX firmware upload (~86KB) must be a continuous
I2C transaction without intermediate STOP conditions.

Arduino ZephyrI2C has a 256-byte ring buffer. Any chunking of the upload into
multiple transactions with STOP between them prevents register 0x06 (sensor MCU
boot complete) from returning 1 — the poll loop hung indefinitely.

#### What Was Tried

**Part 1 — Correct:** Bypass Arduino Wire entirely. hybx_vl53l5cx platform layer
now uses Zephyr's native `i2c_transfer()` API with `struct i2c_msg[]` and direct
buffer pointers. `VL53L5CX_Platform.wire` removed. Replaced with
`VL53L5CX_Platform.i2c_dev` (`const struct device *`). Default:
`DEVICE_DT_GET(DT_NODELABEL(i2c4))`. No `Wire1.begin()` needed in the sketch.

**Part 2 — Insufficient:** `I2C_MSG_STM32_USE_RELOAD_MODE` (BIT(7)) correctly
prevents intermediate START conditions at 255-byte boundaries. However:

The Zephyr STM32 I2C driver enforces `CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC`
(default 500ms) per `i2c_transfer()` call via a kernel semaphore. The VL53L5CX
firmware upload requires a single continuous I2C transaction of up to 32,800
bytes (UM2887 Table 2). At 400kHz, 32KB takes ~0.7 seconds — exceeding the
500ms timeout. The kernel aborts the transfer, leaving the I2C peripheral
disabled.

**Chunking attempted and rejected:** Splitting the upload into sub-500ms chunks
fails because the VL53L5CX page memory resets to the beginning on each new I2C
START condition. Only the last chunk survives. There is no way to chain separate
`i2c_transfer()` calls into a single continuous bus transaction.

#### Why No v1.x Fix Exists

All viable solutions require modifying the Arduino Zephyr board package files:

- `CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC=5000` — overwritten on package update
- `CONFIG_I2C_STM32_V2_DMA=y` + TX DMA channel in overlay — overwritten on update

A post-install script to reapply config changes was considered and rejected as
an unacceptable hack.

#### v2.0 Resolution

The HybX Build System (v2.0) supports DMA via two methods:

1. **Global patch** — Run `scripts/setup-dma-v0.0.1.py` after Arduino package
   install/update. This patches the autoconf.h permanently (until package
   update).

2. **Per-project** — Add `hybx.json` with `kconfig_overrides`:
   ```json
   {
     "kconfig_overrides": {
       "CONFIG_I2C_STM32_V2_DMA": "y",
       "CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC": "5000"
     }
   }
   ```

The compiler patches autoconf.h at build time when `kconfig_overrides` is present.

---

### arduino-app-cli Flashes to RAM Not Flash by Default

**Status:** Open — workaround documented, permanent fix in v2.0
**Affects:** All sketch updates on Arduino UNO Q

#### Problem

`arduino-app-cli app start` uploads sketches to RAM (`flash_sketch_ram.cfg`)
by default. RAM uploads are lost on every MCU reset. The old flash binary
persists and runs on reboot, making it appear that sketch updates have no effect.

The `flash_sketch.cfg` config (writes to `0x8100000` permanently) exists at
`/tmp/remoteocd/flash_sketch.cfg` but is not used by default.

#### Symptom

After multiple `clean` and `start` cycles, the Bridge still reports methods
from the old sketch binary because the old flash image boots on every restart.

#### Workaround

After `arduino-app-cli app start` compiles the new binary, flash it to
permanent flash memory manually:

```bash
/opt/openocd/bin/openocd \
    -s /opt/openocd \
    -s /opt/openocd/share/openocd/scripts \
    -f /opt/openocd/openocd_gpiod.cfg \
    -c "set filename /tmp/remoteocd/sketch.elf-zsk.bin" \
    -f /tmp/remoteocd/flash_sketch.cfg
```

Then restart the app:
```bash
arduino-app-cli app stop ~/Arduino/UNO-Q/<app>
arduino-app-cli app start ~/Arduino/UNO-Q/<app>
```

#### Required Fix (v2.0)

`hybx-flash` will always write to flash memory directly via OpenOCD.
No RAM mode, no mystery, no workaround needed.

---

### start — Existing App Files Not Synced from Repo on Pull

**Status:** Closed — fixed in start-v1.2.0
**Affects:** All apps that have been updated in the repo

#### Problem

`start` pulls the UNO-Q repo on every run but only copies apps that do
not already exist in `~/Arduino/UNO-Q/`. Existing apps were never updated,
meaning sketch and Python file changes in the repo never reached the board.
Manual copies into `~/Arduino/UNO-Q/` were the only way to update existing apps.

#### Symptom

After pushing sketch changes, `Bridge.call()` raises:
```
ValueError: Request 'get_sensor_status' failed: method get_sensor_status not available (2)
```
because the old binary was still on the MCU.

#### Resolution

`start-v1.2.0` now syncs tracked files for existing apps on every pull:
- `sketch/*.ino` — sketch source
- `sketch/*.yaml` — library and platform config
- `python/*.py` — Python app
- `app.yaml`, `README.md` — app metadata

`.cache/` is never touched — it is build state only.

---

### No Silent Failures Policy

**Status:** Active — applies to all HybX libraries and sketches
**Affects:** All code in hybotix repos

Every failure point must be detected and reported. Silent failures —
where a function fails but the caller cannot know — are not acceptable.

#### Requirements

1. **Library layer:** Every ULD/hardware call checks its return value.
   Failures set `hybx_last_error` (error code) and `hybx_last_error_step`
   (which function failed). No `return;` on failure without setting error state.

2. **Sketch layer:** Every library call that can fail checks its return value.
   Failure state is exposed via Bridge functions so the Python side can report it.

3. **Python layer:** Every `Bridge.call()` is wrapped in try/except TimeoutError.
   Every possible response value is explicitly handled — no unhandled cases.
   Parse errors on sensor data are caught and reported with raw data.

4. **Documentation:** Every code change — including bug fixes — is documented
   in the same commit as the code change.

#### Implementation in hybx_vl53l5cx

- `HYBX_ERR_*` step constants identify exactly which ULD call failed
- `hybx_last_error` and `hybx_last_error_step` are public globals
- `_fail(step, uld_status)` records both and returns false
- `get_sensor_status()` Bridge function exposes state as
  `"ready"`, `"initializing"`, `"init_failed:<step>:<code>"`,
  or `"error:<step>:<code>"`
- Python `ERROR_STEPS` dict maps step codes to ULD function names

---

### arduino-app-cli Library Manager — No Support for Library Manager-Only Libraries

**Status:** Closed — resolved via `dir:` sketch.yaml entry + `~/Arduino/libraries/`
**Affects:** All Hybrid RobotiX Arduino libraries not published to the Arduino Library Manager

#### Problem

`arduino-app-cli` resolves library entries in `sketch.yaml` exclusively against
the Arduino Library Manager registry. There is no supported mechanism for listing
a local or git library directly in the `sketch.yaml` libraries section.

Several approaches were investigated and rejected:

- `arduino-cli lib install --git-url` — requires `library.enable_unsafe_install`
  and only installs into `~/Arduino/libraries/`; `arduino-app-cli` does not search
  that path when a profile is active (profile mode locks library search to declared
  libraries only)
- Sketch-local subdirectory — `arduino-cli` only compiles `.cpp` files in the
  sketch root, not subdirectories; subdirectory auto-discovery is an Arduino IDE 2
  feature only, not `arduino-cli`
- `CompileRequest.Libraries` field — `arduino-app-cli`'s `compileUploadSketch()`
  does not populate this field; it is hardwired to use only profile libraries

#### Resolution — `dir:` sketch.yaml Entry

`arduino-cli` sketch profiles support a `dir:` library reference that points to a
local absolute path. This maps to `LocalLibrary` in the RPC and is compiled using
`RecursiveLayout` (all files under `src/` are compiled recursively). Verified in
`arduino-cli` source: `commands/instances.go` lines 373–389.

The library must be installed at the referenced path:
```bash
mkdir -p ~/Arduino/libraries
git clone https://github.com/hybotix/hybx_vl53l5cx.git ~/Arduino/libraries/hybx_vl53l5cx
```

The `sketch.yaml` entry:
```yaml
libraries:
  - dir: /home/arduino/Arduino/libraries/hybx_vl53l5cx
```

The sketch uses angle-bracket include (it is a proper installed library):
```cpp
#include <hybx_vl53l5cx.h>
```

`libs install-git` clones the repo to `~/Arduino/libraries/<lib_name>/`.
`libs embed` records the project association in `libraries.json` and writes the
`dir:` entry into `sketch.yaml` via `rewrite_sketch_yaml()`.
`update` and `start` pull all git-managed repos in `~/Arduino/libraries/` automatically.

#### Additional Fixes Required (v1.2.0)

- `clean-v1.2.0.py`: was not clearing `~/.hybx/sketch_hashes.json`, causing
  `start` to report "Sketch unchanged — skipping recompile" after `clean`. Fixed
  by adding `clear_sketch_hash()` and passing `--compile` to `start`.
- `start-v1.2.0.py` / all commands: `os.system("clear")` was wiping terminal
  context before each command. Removed from all v1.2.0 commands.
- `monitor-vl53l5cx/python/main.py`: `Bridge.call("set_resolution")` timed out
  because `vl53.begin()` blocks the Bridge for up to 10 s during sensor firmware
  upload. Fixed by polling `get_distance_data` until sensor is ready before
  calling `set_resolution`.

---

### update — getcwd Errors on Startup

**Status:** Open — cannot fix (`newrepo.bash` is untouchable)  
**Affects:** Users running `update` from inside `$REPO_DEST`

#### Problem

When `update` runs, it wipes and recreates `$REPO_DEST` as part of the bootstrap sequence. If the shell's current working directory is anywhere inside that path at the time it gets wiped, bash loses track of the current directory and emits:

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory
chdir: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory
```

#### Impact

Cosmetic only. `update` completes successfully despite the errors. All repos are cloned, all bin commands are deployed, all symlinks are relinked.

#### Workaround

Run `update` from a directory that is not inside `$REPO_DEST`:

```bash
cd ~
update
```

#### Required Fix

`newrepo.bash` would need to `cd $HOME` before wiping `$REPO_DEST`. Since `newrepo.bash` is untouchable under any circumstances, this cannot be fixed in the current architecture.

---

### Docker Network Isolation — Local Hostname Resolution Fails

**Status:** Open — waiting for Arduino to fix  
**Filed:** [arduino-app-cli GitHub issue #328](https://github.com/arduino/arduino-app-cli/issues/328)  
**Affects:** All apps that connect to local network services by hostname

#### Problem

Python apps managed by `arduino-app-cli` run inside Docker containers using an isolated network (`arduino-<appname>_default`). This prevents apps from resolving local network hostnames including:

- mDNS hostnames (`*.local`) such as `hybx-test.local`
- Hostnames defined in the host's `/etc/hosts`
- Any hostname resolvable on the local network but not via public DNS

The host's `/etc/hosts` is not inherited by the container, and mDNS multicast does not pass through Docker's network isolation.

#### Symptoms

App logs show:

```
socket.gaierror: [Errno -2] Name or service not known
```

#### What Was Tried

- Adding `extra_hosts` to `app.yaml` — silently ignored, not passed to generated compose file
- Adding hostname to `/etc/hosts` on the UNO Q — not inherited by Docker container
- The generated `.cache/app-compose.yaml` only contains the default `msgpack-rpc-router:host-gateway` entry

#### Impact on SecureSMARS

SecureSMARS cannot connect to the Mosquitto MQTT broker on `hybx-test.local` via the standard `restart` workflow.

#### Workaround (Manual — Not Recommended)

1. Start the app normally with `start <app_path>`
2. Manually edit `.cache/app-compose.yaml` and add to `extra_hosts`:
   ```yaml
   - hybx-test.local:192.168.1.117
   - hybx-test:192.168.1.117
   ```
3. Run: `docker compose -f <app_path>/.cache/app-compose.yaml up -d --force-recreate`

This workaround is not sustainable as the compose file is regenerated on every app start.

#### Required Fix

Arduino needs to implement one of the following:

1. Support `extra_hosts` in `app.yaml` and pass them through to the generated compose file
2. Use `network_mode: host` for the container
3. Document a supported way to configure Docker networking for apps

---

### Infineon optigatrust — I2C Bus Hardcoded to `/dev/i2c-1`

**Status:** Open — waiting for Infineon to fix  
**Filed:** [python-optiga-trust GitHub issue #26](https://github.com/Infineon/python-optiga-trust/issues/26)  
**Affects:** Any system where the OPTIGA Trust M is not on I2C bus 1

#### Problem

The compiled library `liboptigatrust-i2c-linux-aarch64.so` has `/dev/i2c-1` hardcoded. On Raspberry Pi 4B running Debian 13 (Trixie), the OPTIGA Trust M is visible at address 0x30 on `/dev/i2c-21`, but the library always tries `/dev/i2c-1` and fails to connect.

Additionally, the library requires GPIO reset and VDD pins (`GPIO_PIN_RESET 17`, `GPIO_PIN_VDD 27`) which are hardcoded and not needed when using the Adafruit breakout board directly.

#### Symptoms

```
Failed to open gpio direction for writing!
Trying to open i2c interface: FAIL
ERROR optigatrust._backend i2c: Failed to connect
```

#### What Was Tried

- Creating symlink `/dev/i2c-1 -> /dev/i2c-21` — library still fails
- Running as root — still fails
- Verified Trust M responds correctly: `i2cget -y 21 0x30 0x00` returns `0x00`
- The source file `extras/pal/linux/target/rpi3/pal_ifx_i2c_config.c` confirms hardcoded path

#### Impact on SecureSMARS

The Trust M on the MQTT broker Pi cannot be used for encrypted MQTT authentication until Infineon fixes the library.

#### Required Fix

In `pal_ifx_i2c_config.c`, the I2C device path should be read from an environment variable:

```c
const char *env = getenv("OPTIGA_I2C_DEV");
if (env != NULL) {
    strncpy(i2c_dev, env, sizeof(i2c_dev) - 1);
}
```

GPIO pins should also be made optional (set to `-1` to disable).

---

*Hybrid RobotiX — San Diego*

---

## Wire1.begin() hangs MCU after Bridge.begin()

**Status:** Confirmed — workaround in place  
**Affects:** Arduino UNO Q, any sketch using Wire1 (QWIIC) with RouterBridge  

Calling `Wire1.begin()` after `Bridge.begin()` hangs the MCU permanently. No error is reported — the MCU simply stops executing. The Bridge never responds.

**Root cause:** Unknown — likely a Zephyr RTOS resource conflict between the RouterBridge serial driver and the Wire1/i2c4 peripheral initialization.

**Workaround:** Never call `Wire1.begin()`. Wire1 works on the UNO Q without explicit initialization. Libraries that call `Wire1.begin()` internally (like SparkFun VL53L5CX) must be replaced with implementations that skip the `begin()` call.

**Confirmed working pattern:**
```cpp
void setup() {
    Bridge.begin();
    Bridge.provide("my_func", my_func);
    // Wire1.begin() — NEVER CALL THIS
    Wire1.beginTransmission(0x29);  // Works fine without begin()
    ...
}
```

---

## Zephyr native i2c_transfer() hangs with RouterBridge

**Status:** Confirmed — replaced with Wire1  
**Affects:** Arduino UNO Q, any sketch using Zephyr native I2C with RouterBridge  

Using `i2c_transfer()`, `i2c_write()`, or `i2c_write_read()` from `<zephyr/drivers/i2c.h>` during large I2C transfers (e.g. VL53L5CX 96KB firmware upload) causes the MCU to hang indefinitely when RouterBridge is running.

**Root cause:** The Zephyr STM32 I2C kernel driver has a 500ms transfer timeout (`CONFIG_I2C_STM32_TRANSFER_TIMEOUT_MSEC`). Using `I2C_MSG_STM32_USE_RELOAD_MODE` to bypass chunking causes the hardware to deadlock. Chunking at 255–4096 bytes triggers the timeout and hangs.

**Workaround:** Use Wire1 directly instead of Zephyr native I2C. See hybx_vl53l5cx `platform.cpp` for the Wire1 implementation.

---

## Sketch hash does not detect library changes

**Status:** Known limitation  
**Affects:** All HybX apps using external libraries  

The HybX sketch hash (`~/.hybx/sketch_hashes.json`) only tracks changes to `.ino` sketch files. If a library changes (e.g. `hybx_vl53l5cx`), `start` will not detect the change and will skip recompile, leaving the old binary on the MCU.

**Workaround:** Always use `clean <app>` after updating a library. `clean` passes `--compile` to `start`, forcing a full recompile regardless of the sketch hash.

```bash
update
board sync --force  
clean <app>
mon
```
