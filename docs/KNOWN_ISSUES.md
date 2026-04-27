# HybX Development System — Known Issues
## Hybrid RobotiX

> *Hybrid RobotiX designs and creates intelligent technologies that empower people facing physical and accessibility challenges to live more independently and achieve more on their own terms.*

---

## Open Issues

---

### arduino-app-cli Library Manager — No Support for Local or Git Libraries

**Status:** Closed — by design (HybX library workflow)
**Affects:** All Hybrid RobotiX Arduino libraries not published to the Arduino Library Manager

#### Problem

`arduino-app-cli` resolves library entries in `sketch.yaml` exclusively against
the Arduino Library Manager registry. There is no override, no local path support,
and no git URL support in the `sketch.yaml` library section.

Attempting to install a local library via `arduino-cli lib install --git-url` and
then listing it in `sketch.yaml` fails with:

```
[INFO] Error: code:9 message:"Library 'hybx_vl53l5cx' not found"
```

The `--git-url` flag also requires enabling `library.enable_unsafe_install` in the
arduino-cli configuration, which is off by default.

#### Resolution — HybX Library Workflow

The Arduino build system supports **sketch-local libraries** natively: any `.cpp`
files found in subdirectories of the sketch folder are compiled automatically. This
is the correct, designed-in mechanism for libraries not in the Library Manager.

The HybX Development System (v1.2.0) formalises this with two new `libs` subcommands:

```bash
# Install the HybX library repo onto the board
libs install-git https://github.com/hybotix/hybx_vl53l5cx.git

# Embed the library source into a project sketch folder
libs embed monitor-vl53l5cx hybx_vl53l5cx
```

`libs install-git` clones the repo to `~/Arduino/hybx_libraries/<lib_name>/`.
`libs embed` copies `src/` into `<apps_path>/<project>/sketch/<lib_name>/` and
records the embedding in `libraries.json`.

The library is **not listed in `sketch.yaml`** — `arduino-app-cli` never sees it
as a library dependency. Instead the sketch uses a relative `#include`:

```cpp
#include "hybx_vl53l5cx/hybx_vl53l5cx.h"
```

`update` and `start` both automatically pull all repos in `~/Arduino/hybx_libraries/`
to keep embedded library source in sync with the upstream repo.

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
