"""Compatibility startup entrypoint.

Running `python main.py` starts the API service by default.
"""

from __future__ import annotations

import sys

from remote_sensing_tools.cli import main as cli_main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("serve")
    raise SystemExit(cli_main())
