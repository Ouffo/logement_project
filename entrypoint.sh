#!/bin/bash
set -e

Xvfb :99 -screen 0 1280x720x24 &
export DISPLAY=:99

exec "$@"