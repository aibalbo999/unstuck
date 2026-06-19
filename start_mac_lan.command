#!/bin/bash
# Start the local app with trusted Wi-Fi / phone access enabled.

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export LAN_ACCESS=1
exec "$DIR/start_mac.command"
