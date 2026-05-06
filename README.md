# fastcs-demo

A small, self-contained project that turns the FastCS tutorials into a runnable
demo IOC. It exists to verify that the FastCS documentation and code stay in
working order: the controller is the one built up across
[`docs/tutorials/static-drivers.md`](https://diamondlightsource.github.io/FastCS/main/tutorials/static-drivers.html),
and the multi-controller setup follows
[`docs/how-to/launch-framework.md`](https://diamondlightsource.github.io/FastCS/main/how-to/launch-framework.html#hosting-multiple-controllers).

## What it does

`fastcs.yaml` hosts two `TemperatureController` instances side-by-side:

| Id     | Sim port | Ramps |
|--------|----------|-------|
| `MAIN` | 25565    | 4     |
| `AUX`  | 25566    | 2     |

A bundled `tickit` config (`src/fastcs_demo/simulation/temp_controller.yaml`)
brings up both simulators on those ports. The `fastcs[demo]` extra is what
provides `tickit` and the `TempController` simulator device class.

## Install

```bash
uv sync
```

## Run

In one terminal, start the simulators:

```bash
./launch-sim.sh
```

(thin wrapper around `tickit all src/fastcs_demo/simulation/temp_controller.yaml`).

In another terminal, start the IOC:

```bash
./launch-ioc.sh
```

(equivalent to `python -m fastcs_demo run fastcs.yaml`, but it activates the
project's `.venv` if present and pins EPICS CA addressing to loopback so the
IOC doesn't broadcast on every interface).

You should now have two PV trees published over EPICS CA:

```bash
caget MAIN:RampRate_RBV AUX:RampRate_RBV
caget MAIN:R1:Start_RBV AUX:R1:Start_RBV
caput MAIN:R1:Enabled On
caget MAIN:Power
```

A set of `*.bob` files is written into `opi/` — one per controller and
sub-controller, plus an `opi/index.bob` that links them.

## Open the screens in Phoebus

`launch-phoebus.sh` runs the
[`ec-phoebus`](https://github.com/epics-containers/ec-phoebus) container under
podman with `--net host`, mounts this project's `opi/` folder, and opens
`opi/index.bob`:

```bash
./launch-phoebus.sh
```

It needs an X11 display and `xauth`; the script forwards a per-user xauth
cookie into the container. Drop a `settings.ini` next to the script to override
Phoebus settings (it gets bind-mounted on top of the default the same way the
upstream `phoebus.sh` does it).

## Run the smoke test

```bash
pytest -q
```

The test boots tickit + the IOC under subprocesses, then reads PVs from both
prefixes via `aioca` to confirm the whole stack is wired up end-to-end.
