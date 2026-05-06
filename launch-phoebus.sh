#!/usr/bin/env bash
# Launch Phoebus (via the ec-phoebus container image) opened on this project's
# generated `opi/index.bob` screen.
#
# See https://github.com/epics-containers/ec-phoebus for the upstream image
# and the original launcher this script is modelled on.
#
# Requirements: podman, an X11 display, xauth. Uses --net host so Phoebus can
# talk to the IOC running on localhost.

set -euo pipefail

here=$(realpath "$(dirname "$0")")
opi_dir=${here}/opi
target=opi/index.bob

if [[ ! -f ${here}/${target} ]]; then
    echo "error: ${here}/${target} not found." >&2
    echo "Start the IOC once to generate it: python -m fastcs_demo run fastcs.yaml" >&2
    exit 1
fi

# X11 forwarding via a per-user xauth cookie that the container can read.
xauth_file=/tmp/.container.xauth.${USER}
touch "${xauth_file}"
xauth nlist "${DISPLAY}" | sed -e 's/^..../ffff/' | xauth -f "${xauth_file}" nmerge -
chmod 600 "${xauth_file}"

image=ghcr.io/epics-containers/ec-phoebus:latest

mounts=(
    -v "/tmp:/tmp"
    -v "${here}:/workspace"
    -v "${opi_dir}:/workspace/opi"
)

# Mount settings.ini next to this script if present, the same way upstream does.
if [[ -f ${here}/settings.ini ]]; then
    mounts+=(-v "${here}/settings.ini:/settings/settings.ini")
fi

x11=(
    -e DISPLAY
    -e "XAUTHORITY=${xauth_file}"
    -v "${xauth_file}:${xauth_file}"
    --net host
)

set -x
exec podman run --rm -it \
    --pull newer \
    --security-opt=label=type:container_runtime_t \
    "${mounts[@]}" \
    "${x11[@]}" \
    "${image}" \
    -settings /settings/settings.ini \
    -resource "/workspace/${target}" \
    "$@"
