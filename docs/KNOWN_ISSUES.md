# HybX Development System — Known Issues
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Open Issues

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
