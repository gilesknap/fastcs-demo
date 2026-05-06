"""Tutorial temperature controller, lightly adapted for ``launch()``.

The body of this file is the controller built up across
``docs/tutorials/static-drivers.md`` (the final ``static15.py`` snippet). The
only structural change is wrapping the two ``__init__`` arguments in a single
``TemperatureControllerSettings`` dataclass, because ``fastcs.launch.launch``
requires the controller's ``__init__`` to take at most one (type-hinted)
options argument besides ``self``.

When ``launch()`` instantiates this controller from ``fastcs.yaml`` it stamps
the dict-key id (e.g. ``MAIN``, ``AUX``) onto the controller, and that id is
used as the EPICS PV prefix.
"""

from __future__ import annotations

import asyncio
import enum
import json
from dataclasses import KW_ONLY, dataclass
from typing import TypeVar

from fastcs.attributes import AttributeIO, AttributeIORef, AttrR, AttrRW, AttrW
from fastcs.connections import IPConnection, IPConnectionSettings
from fastcs.controllers import Controller
from fastcs.datatypes import Enum, Float, Int, String
from fastcs.logging import logger
from fastcs.methods import command, scan

NumberT = TypeVar("NumberT", int, float)


class OnOffEnum(enum.StrEnum):
    Off = "0"
    On = "1"


@dataclass
class TemperatureControllerSettings:
    """Single options object expected by the launch framework."""

    num_ramp_controllers: int
    ip_settings: IPConnectionSettings


@dataclass
class TemperatureControllerAttributeIORef(AttributeIORef):
    name: str
    _: KW_ONLY
    update_period: float | None = 0.2


class TemperatureControllerAttributeIO(
    AttributeIO[NumberT, TemperatureControllerAttributeIORef]
):
    def __init__(self, connection: IPConnection, suffix: str = "") -> None:
        super().__init__()
        self._connection = connection
        self._suffix = suffix

    async def update(
        self, attr: AttrR[NumberT, TemperatureControllerAttributeIORef]
    ) -> None:
        query = f"{attr.io_ref.name}{self._suffix}?"
        response = await self._connection.send_query(f"{query}\r\n")
        value = response.strip("\r\n")

        self.log_event("Query for attribute", query=query, response=value, topic=attr)
        await attr.update(attr.dtype(value))

    async def send(
        self,
        attr: AttrW[NumberT, TemperatureControllerAttributeIORef],
        value: NumberT,
    ) -> None:
        cmd = f"{attr.io_ref.name}{self._suffix}={attr.dtype(value)}"
        logger.info("Sending attribute value", command=cmd, attribute=attr)
        await self._connection.send_command(f"{cmd}\r\n")


class TemperatureRampController(Controller):
    start = AttrRW(Int(), io_ref=TemperatureControllerAttributeIORef("S"))
    end = AttrRW(Int(), io_ref=TemperatureControllerAttributeIORef("E"))
    enabled = AttrRW(Enum(OnOffEnum), io_ref=TemperatureControllerAttributeIORef("N"))
    target = AttrR(Float(prec=3), io_ref=TemperatureControllerAttributeIORef("T"))
    actual = AttrR(Float(prec=3), io_ref=TemperatureControllerAttributeIORef("A"))
    voltage = AttrR(Float(prec=3))

    def __init__(self, index: int, connection: IPConnection) -> None:
        suffix = f"{index:02d}"
        super().__init__(
            f"Ramp{suffix}",
            ios=[TemperatureControllerAttributeIO(connection, suffix)],
        )


class TemperatureController(Controller):
    device_id = AttrR(String(), io_ref=TemperatureControllerAttributeIORef("ID"))
    power = AttrR(Float(), io_ref=TemperatureControllerAttributeIORef("P"))
    ramp_rate = AttrRW(Float(), io_ref=TemperatureControllerAttributeIORef("R"))

    def __init__(self, settings: TemperatureControllerSettings) -> None:
        self._settings = settings
        self._connection = IPConnection()

        super().__init__(ios=[TemperatureControllerAttributeIO(self._connection)])

        self._ramp_controllers: list[TemperatureRampController] = []
        for index in range(1, settings.num_ramp_controllers + 1):
            ramp = TemperatureRampController(index, self._connection)
            self._ramp_controllers.append(ramp)
            self.add_sub_controller(f"R{index}", ramp)

    async def connect(self) -> None:
        await self._connection.connect(self._settings.ip_settings)
        # Base Controller.connect() sets _connected; override must do the same
        # or the periodic scan loop in controllers/controller.py:147 stays
        # paused forever.
        self._connected = True

    async def close(self) -> None:
        await self._connection.close()

    @scan(0.1)
    async def update_voltages(self) -> None:
        voltages = json.loads(
            (await self._connection.send_query("V?\r\n")).strip("\r\n")
        )
        for index, ramp in enumerate(self._ramp_controllers):
            await ramp.voltage.update(float(voltages[index]))

    @command()
    async def disable_all(self) -> None:
        self.log_event("Disabling all ramps")
        for ramp in self._ramp_controllers:
            await ramp.enabled.put(OnOffEnum.Off, sync_setpoint=True)
            # The simulator gets confused if requests are concatenated, so pace them.
            await asyncio.sleep(0.1)
