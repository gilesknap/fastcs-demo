#!/usr/bin/env bash
# Launch the demo IOC interactively against fastcs.yaml.
#
# Activates the project's `.venv` if it exists (so this works straight after
# `pip install -e .` into that venv) and otherwise falls back to whatever
# `python` is on PATH. The launcher's interactive IPython shell is left
# attached to this terminal — Ctrl-D / `exit` to shut the IOC down cleanly.

set -euo pipefail

here=$(realpath "$(dirname "$0")")
cd "${here}"

if [[ -x .venv/bin/python ]]; then
    python=.venv/bin/python
else
    python=$(command -v python3 || command -v python)
fi

# Pin EPICS CA to loopback by default so the IOC doesn't broadcast on every
# interface in dev containers. Override by exporting these before invoking.
: "${EPICS_CA_AUTO_ADDR_LIST:=NO}"
: "${EPICS_CAS_INTF_ADDR_LIST:=127.0.0.1}"
: "${EPICS_CA_ADDR_LIST:=127.0.0.1}"
export EPICS_CA_AUTO_ADDR_LIST EPICS_CAS_INTF_ADDR_LIST EPICS_CA_ADDR_LIST

exec "${python}" -m fastcs_demo run fastcs.yaml "$@"
