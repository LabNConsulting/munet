#!/bin/sh
set -e
printf '%s\n' "$@"
test -s /mnt/flash/startup-config
test -s /mnt/flash/system_mac_address
touch /ceos-ready
exec sleep 600
