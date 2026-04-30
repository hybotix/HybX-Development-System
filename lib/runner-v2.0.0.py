"""
runner-v2.0.0.py
Hybrid RobotiX — HybX Development System v2.0
Dale Weber <hybotix@hybridrobotix.io>

HybXRunner — replaces arduino-app-cli container management.

Starts, stops, and monitors the Docker container that runs an app's
Python side. Derived by inspecting arduino-app-cli's container config.

Container spec (from docker inspect):
  Image:      ghcr.io/arduino/app-bricks/python-apps-base:0.8.0
  Mounts:     ~/Arduino/<board>/<app> -> /app
              /var/run/arduino-router.sock -> /var/run/arduino-router.sock
              /sys/class/leds/* -> /sys/class/leds/*
  ExtraHosts: msgpack-rpc-router:host-gateway
  Groups:     44, 29, 991, 20, 1001
  Network:    arduino-<board>-<app>_default
  LogConfig:  json-file, max-size=5m, max-file=2

Usage:
    from runner import HybXRunner
    runner = HybXRunner(board_name, app_path)
    runner.start()
    runner.stop()
    runner.logs()   # streams logs to stdout

License: MIT
"""

import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional


PYTHON_APP_IMAGE = "ghcr.io/arduino/app-bricks/python-apps-base:0.8.0"

LED_MOUNTS = [
    "/sys/class/leds/blue:user",
    "/sys/class/leds/green:user",
    "/sys/class/leds/red:user",
    "/sys/class/leds/blue:bt",
    "/sys/class/leds/green:wlan",
    "/sys/class/leds/red:panic",
]

ROUTER_SOCK = "/var/run/arduino-router.sock"
EXTRA_HOST  = "msgpack-rpc-router:host-gateway"
ADD_GROUPS  = ["44", "29", "991", "20", "1001"]


@dataclass
class RunnerResult:
    success: bool
    message: str = ""
    elapsed: float = 0.0


class HybXRunner:
    """
    Manages the Docker container lifecycle for a HybX app.
    Replaces arduino-app-cli app start/stop/logs.
    """

    def __init__(self, board_name: str, app_path: str):
        self.board_name  = board_name.lower().replace("_", "-")
        self.app_path    = os.path.expanduser(app_path)
        self.app_name    = os.path.basename(self.app_path)
        self.container   = f"arduino-{self.board_name}-{self.app_name}-main-1"
        self.network     = f"arduino-{self.board_name}-{self.app_name}_default"

    def _run(self, cmd: list, capture: bool = True) -> tuple[int, str]:
        result = subprocess.run(cmd, capture_output=capture, text=True)
        out = (result.stdout or "") + (result.stderr or "")
        return result.returncode, out.strip()

    def _container_exists(self) -> bool:
        code, _ = self._run(["docker", "inspect", self.container])
        return code == 0

    def _network_exists(self) -> bool:
        code, _ = self._run(["docker", "network", "inspect", self.network])
        return code == 0

    def _ensure_network(self):
        if not self._network_exists():
            self._run(["docker", "network", "create", self.network])

    def stop(self) -> RunnerResult:
        """Stop and remove the app container."""
        t0 = time.time()
        self._run(["docker", "rm", "-f", self.container])
        return RunnerResult(success=True, elapsed=time.time() - t0)

    def start(self) -> RunnerResult:
        """Start the app container."""
        t0 = time.time()

        # Stop any existing container
        self.stop()

        # Ensure network exists
        self._ensure_network()

        cmd = [
            "docker", "run",
            "--name",    self.container,
            "--network", self.network,
            "--add-host", EXTRA_HOST,
            "--log-driver", "json-file",
            "--log-opt", "max-size=5m",
            "--log-opt", "max-file=2",
            "-d",  # detached
        ]

        # App mount
        cmd += ["-v", f"{self.app_path}:/app"]

        # Router socket
        if os.path.exists(ROUTER_SOCK):
            cmd += ["-v", f"{ROUTER_SOCK}:{ROUTER_SOCK}"]

        # LED mounts
        for led in LED_MOUNTS:
            if os.path.exists(led):
                cmd += ["-v", f"{led}:{led}"]

        # Group add
        for g in ADD_GROUPS:
            cmd += ["--group-add", g]

        cmd.append(PYTHON_APP_IMAGE)

        code, out = self._run(cmd)
        if code != 0:
            return RunnerResult(success=False, message=out,
                                elapsed=time.time() - t0)

        return RunnerResult(success=True, elapsed=time.time() - t0)

    def logs(self, follow: bool = True):
        """Stream container logs to stdout."""
        cmd = ["docker", "logs"]
        if follow:
            cmd.append("-f")
        cmd.append(self.container)
        subprocess.run(cmd)
