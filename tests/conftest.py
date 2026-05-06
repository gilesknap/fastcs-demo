"""Pytest fixtures that boot the simulators and the demo IOC.

The fixtures are session-scoped so the smoke test can spend its time on
PV reads instead of paying startup costs per-test. Subprocess output is piped
into the test runner via threads so the buffers can never fill up and
deadlock.
"""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SIM_YAML = PROJECT_ROOT / "src/fastcs_demo/simulation/temp_controller.yaml"
FASTCS_YAML = PROJECT_ROOT / "fastcs.yaml"
SIM_PORTS = (25565, 25566)


def _wait_for_port(port: int, deadline: float) -> None:
    """Block until something is accepting connections on ``localhost:port``."""
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"Nothing listening on localhost:{port}")


def _drain(stream, prefix: str) -> None:
    for line in iter(stream.readline, ""):
        sys.stderr.write(f"[{prefix}] {line}")
        sys.stderr.flush()
    stream.close()


def _wait_for_log(stream, needle: str, deadline: float, prefix: str) -> None:
    while time.monotonic() < deadline:
        line = stream.readline()
        if not line:
            time.sleep(0.05)
            continue
        sys.stderr.write(f"[{prefix}] {line}")
        sys.stderr.flush()
        if needle in line:
            return
    raise TimeoutError(f"Did not see '{needle}' from {prefix}")


@pytest.fixture(scope="session")
def simulators() -> Iterator[None]:
    """Run ``tickit all`` against the bundled simulator config."""
    proc = subprocess.Popen(
        ["tickit", "all", str(SIM_YAML)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    drain = threading.Thread(target=_drain, args=(proc.stdout, "tickit"), daemon=True)
    drain.start()

    try:
        deadline = time.monotonic() + 30
        for port in SIM_PORTS:
            _wait_for_port(port, deadline)
        yield
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="session")
def ioc(simulators) -> Iterator[None]:
    """Run ``python -m fastcs_demo run fastcs.yaml``.

    Pinned to localhost EPICS addressing so CA traffic stays on the loopback
    interface — important for CI/dev containers without broadcast routing.
    """
    env = {
        **os.environ,
        "EPICS_CA_AUTO_ADDR_LIST": "NO",
        "EPICS_CA_ADDR_LIST": "127.0.0.1",
        "EPICS_CAS_INTF_ADDR_LIST": "127.0.0.1",
    }
    # The launch CLI puts an IPython shell on stdin. Give it a real PIPE we
    # never close so the shell never sees EOF and shuts the IOC down on us.
    proc = subprocess.Popen(
        [sys.executable, "-m", "fastcs_demo", "run", str(FASTCS_YAML)],
        cwd=PROJECT_ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    try:
        _wait_for_log(proc.stdout, "Running IOC", time.monotonic() + 30, "ioc")
        # Drain remaining output so the buffer never blocks the IOC.
        threading.Thread(target=_drain, args=(proc.stdout, "ioc"), daemon=True).start()
        # Give update loops one or two cycles to populate readback values.
        time.sleep(1.0)
        yield
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="session", autouse=True)
def _ca_env() -> Iterator[None]:
    """Match the IOC's CA settings in the test process."""
    saved = {k: os.environ.get(k) for k in (
        "EPICS_CA_AUTO_ADDR_LIST",
        "EPICS_CA_ADDR_LIST",
    )}
    os.environ["EPICS_CA_AUTO_ADDR_LIST"] = "NO"
    os.environ["EPICS_CA_ADDR_LIST"] = "127.0.0.1"
    yield
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
