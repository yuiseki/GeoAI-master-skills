#!/bin/bash
# systemd-run is absent here; cap virtual memory and wall time instead.
ulimit -v 14000000
exec timeout 1500 uvx "$@"
