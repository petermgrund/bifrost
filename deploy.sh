#!/usr/bin/env bash
# Deploy bifrost to the Pi (eir). Run from the dev checkout (Mac Studio):
# pushes the current branch, then pulls + rebuilds + restarts on the Pi.
#
# The Pi checkout at /opt/stacks/bifrost is a DEPLOY TARGET — never edit it
# in place. If someone does, git pull --ff-only refuses and this script stops.
set -euo pipefail

PI=${PI:-peter@192.168.1.69}

git push
ssh "$PI" 'set -e; cd /opt/stacks/bifrost && git pull --ff-only && docker compose build && docker compose up -d'
echo "deployed $(git rev-parse --short HEAD) to $PI"
