"""End-to-end smoke test for the multi-controller demo.

Boots tickit (two simulators on different TCP ports) and the FastCS IOC, then
verifies that PVs from *both* controller prefixes (`MAIN`, `AUX`) are
populated by their respective simulators. If this passes, the tutorial
controller, the launch framework, and the multi-controller wiring are all
working end-to-end.
"""

from __future__ import annotations

import asyncio

import pytest
from aioca import caget, caput, purge_channel_caches

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True, scope="module")
def _purge_ca_caches():
    yield
    # aioca caches per-event-loop, so purge between modules to avoid leaks.
    purge_channel_caches()


async def _read(pv: str, timeout: float = 5.0):
    return await caget(pv, timeout=timeout)


def _decode_long_string(value) -> str:
    """FastCS publishes string attrs as longStringIn (CHAR waveform)."""
    return bytes(value).rstrip(b"\x00").decode("utf-8")


async def test_main_controller_prefix(ioc):
    """MAIN controller should answer with the simulator's device id."""
    device_id = await _read("MAIN:DeviceId")
    assert _decode_long_string(device_id) == "SIMTCONT123"


async def test_aux_controller_prefix(ioc):
    """AUX controller is wired to the second simulator on a different port."""
    device_id = await _read("AUX:DeviceId")
    assert _decode_long_string(device_id) == "SIMTCONT123"


async def test_both_controllers_have_distinct_ramps(ioc):
    """fastcs.yaml gives MAIN 4 ramps and AUX 2 ramps. Verify both extremes."""
    # MAIN should have R4 (it has 4 ramps).
    main_r4_start = await _read("MAIN:R4:Start_RBV")
    assert main_r4_start == 10  # default_start in temp_controller.yaml

    # AUX has only 2 ramps; R2 should exist with its own default.
    aux_r2_start = await _read("AUX:R2:Start_RBV")
    assert aux_r2_start == 5  # AUX default_start


async def test_writes_round_trip_per_controller(ioc):
    """Independently set ramp_rate on each controller and read back."""
    await caput("MAIN:RampRate", 7.5, wait=True, timeout=5.0)
    await caput("AUX:RampRate", 3.25, wait=True, timeout=5.0)

    # Give the update loop a tick to refresh the _RBV.
    await asyncio.sleep(0.5)

    main_rbv = await _read("MAIN:RampRate_RBV")
    aux_rbv = await _read("AUX:RampRate_RBV")

    assert float(main_rbv) == pytest.approx(7.5)
    assert float(aux_rbv) == pytest.approx(3.25)


async def test_disable_all_command_exists(ioc):
    """The tutorial @command should be reachable as a PV on both prefixes."""
    # Calling the command is sufficient — the simulator will accept N0x=0.
    await caput("MAIN:DisableAll", 1, wait=True, timeout=5.0)
    await caput("AUX:DisableAll", 1, wait=True, timeout=5.0)
