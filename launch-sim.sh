#!/usr/bin/env bash
# Launch the tickit simulator backing the demo IOC.
#
# Brings up two `TempController` simulators on TCP ports 25565 (MAIN) and
# 25566 (AUX), matching the controllers in `fastcs.yaml`. Run this in one
# terminal and `./launch-ioc.sh` in another.

set -euo pipefail

here=$(realpath "$(dirname "$0")")
cd "${here}"

if [[ -x .venv/bin/tickit ]]; then
    tickit=.venv/bin/tickit
else
    tickit=$(command -v tickit)
fi

config=src/fastcs_demo/simulation/temp_controller.yaml

exec "${tickit}" all "${config}" "$@"
