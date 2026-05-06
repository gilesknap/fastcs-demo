"""Entrypoint for ``python -m fastcs_demo``.

Hands off to ``fastcs.launch.launch`` with the tutorial controller. The
launcher discovers ``__init__`` types and produces the ``run`` / ``schema`` /
``--version`` CLI documented in
``docs/how-to/launch-framework.md``.
"""

from fastcs.launch import launch

from . import __version__
from .controllers import TemperatureController


def main() -> None:
    launch(TemperatureController, version=__version__)


if __name__ == "__main__":
    main()
