"""
hybx_app.py
Hybrid RobotiX — HybX Development System

Native replacement for arduino.app_utils.
Provides Bridge and App — the complete UNO Q Python runtime.

No Docker. No arduino-app-cli. No arduino.app_utils.
Runs as a plain Python process on the UNO Q Linux side.

Usage in main.py:
    from hybx_app import Bridge, App

    def loop():
        result = Bridge.call("my_function", "arg1", "arg2")
        print(result)

    App.run(user_loop=loop)

Bridge.call() signature:
    Bridge.call(method, *args, timeout=30)

    method  -- str: name of the Bridge function registered in the sketch
    *args   -- any number of positional arguments (strings, numbers)
    timeout -- seconds to wait for MCU response (default 30)

    Returns the result string from the MCU on success.
    Raises BridgeError on MCU error or timeout.

App.run() signature:
    App.run(user_loop)

    user_loop -- callable: your loop() function, called repeatedly
    Runs until Ctrl+C or SIGTERM. Always cleans up gracefully.

Wire protocol (verified by prober.py):
    Request:  [0, msgid, method, [args]]  -- msgpack array
    Response: [1, msgid, error,  result]  -- msgpack array
    Error:    [error_code, error_message] -- on failure, error is this list
    Result:   None on error, value on success

License: MIT
"""

import os
import signal
import socket
import sys
import threading
import time

try:
    import msgpack
except ImportError:
    print("ERROR: msgpack not installed.")
    print("       pip install msgpack --break-system-packages")
    print("       or: <venv>/bin/pip install msgpack")
    sys.exit(1)


# ── Constants ──────────────────────────────────────────────────────────────────

ROUTER_SOCK     = "/var/run/arduino-router.sock"
DEFAULT_TIMEOUT = 30.0    # seconds — matches arduino.app_utils default
LOOP_INTERVAL   = 0.001   # 1ms between loop() calls — matches original behavior


# ── Exceptions ─────────────────────────────────────────────────────────────────

class BridgeError(Exception):
    """Raised when the MCU returns an error or the call times out."""
    pass


# ── Bridge ─────────────────────────────────────────────────────────────────────

class _Bridge:
    """
    Manages the msgpack-RPC connection to the arduino-router.

    Each call opens a fresh connection, sends the request, reads the
    response, and closes. This matches arduino.app_utils behavior and
    keeps the implementation simple and stateless.

    Thread-safe: a lock serializes concurrent calls.
    """

    def __init__(self):
        self._lock   = threading.Lock()
        self._msgid  = 0

    def _next_msgid(self) -> int:
        self._msgid = (self._msgid + 1) & 0xFFFFFFFF
        return self._msgid

    def call(self, method: str, *args, timeout: float = DEFAULT_TIMEOUT):
        """
        Call a Bridge function registered in the sketch.

        method  -- name of the Bridge.provide() function
        *args   -- arguments to pass (strings, numbers)
        timeout -- seconds to wait for response

        Returns the result value from the MCU (typically a string).
        Raises BridgeError on MCU error, timeout, or connection failure.
        """
        with self._lock:
            msgid   = self._next_msgid()
            request = msgpack.packb([0, msgid, method, list(args)],
                                    use_bin_type=True)

            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect(ROUTER_SOCK)
            except FileNotFoundError:
                raise BridgeError(
                    f"Router socket not found: {ROUTER_SOCK}\n"
                    f"Is the arduino-router running?"
                )
            except Exception as e:
                raise BridgeError(f"Could not connect to router: {e}")

            try:
                sock.sendall(request)

                # Read response — accumulate until we can decode a full message
                buf      = b""
                unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)

                while True:
                    try:
                        chunk = sock.recv(4096)
                    except socket.timeout:
                        raise BridgeError(
                            f"Timeout waiting for response to '{method}' "
                            f"(>{timeout}s)"
                        )

                    if not chunk:
                        raise BridgeError(
                            f"Router closed connection before responding to '{method}'"
                        )

                    buf += chunk
                    unpacker.feed(chunk)

                    try:
                        msg = unpacker.unpack()
                    except (msgpack.exceptions.UnpackValueError,
                            msgpack.exceptions.OutOfData):
                        # Incomplete message — read more
                        continue

                    # msg should be [1, msgid, error, result]
                    if not isinstance(msg, list) or len(msg) != 4:
                        raise BridgeError(
                            f"Unexpected response format: {msg!r}"
                        )

                    msg_type, resp_id, error, result = msg

                    if msg_type != 1:
                        raise BridgeError(
                            f"Expected response type 1, got {msg_type}"
                        )

                    if resp_id != msgid:
                        raise BridgeError(
                            f"Message ID mismatch: sent {msgid}, got {resp_id}"
                        )

                    if error is not None:
                        # error is [code, message]
                        if isinstance(error, (list, tuple)) and len(error) >= 2:
                            raise BridgeError(
                                f"MCU error calling '{method}': {error[1]}"
                            )
                        raise BridgeError(
                            f"MCU error calling '{method}': {error!r}"
                        )

                    return result

            finally:
                sock.close()


# ── App ────────────────────────────────────────────────────────────────────────

class _App:
    """
    HybX application runtime.

    Replaces arduino.app_utils App.run().
    Calls user_loop() repeatedly until Ctrl+C or SIGTERM.
    Handles signals cleanly — no zombie processes, no stale sockets.
    """

    def __init__(self):
        self._running  = False
        self._on_stop  = []    # list of callables to run on shutdown

    def on_stop(self, fn):
        """
        Register a cleanup function to call on shutdown.
        Called in LIFO order when App stops.

        Usage:
            App.on_stop(my_cleanup_fn)
        """
        self._on_stop.append(fn)

    def stop(self):
        """Signal the run loop to stop cleanly."""
        self._running = False

    def run(self, user_loop):
        """
        Run user_loop() repeatedly until stopped.

        user_loop -- callable: your loop() function

        Installs SIGINT and SIGTERM handlers.
        Calls registered on_stop() handlers on exit.
        Exceptions in user_loop() are caught, printed, and the loop continues
        — matching arduino.app_utils behavior.
        """
        self._running = True

        def _shutdown(sig, frame):
            print("\n[hybx_app] Stopping...")
            self._running = False

        signal.signal(signal.SIGINT,  _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        print("[hybx_app] Running. Press Ctrl+C to stop.")

        try:
            while self._running:
                try:
                    user_loop()
                except BridgeError as e:
                    print(f"[hybx_app] BridgeError: {e}")
                    time.sleep(1.0)
                except Exception as e:
                    print(f"[hybx_app] Exception in loop(): {e}")
                    time.sleep(1.0)
                time.sleep(LOOP_INTERVAL)
        finally:
            # Run cleanup handlers in reverse registration order
            for fn in reversed(self._on_stop):
                try:
                    fn()
                except Exception as e:
                    print(f"[hybx_app] Cleanup error: {e}")

            print("[hybx_app] Stopped.")


# ── Module-level singletons ────────────────────────────────────────────────────
# Matches arduino.app_utils usage: Bridge.call(), App.run()

Bridge = _Bridge()
App    = _App()
