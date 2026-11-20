#!/bin/sh
# The node shell overrides this shebang.
[[ -f /boot-ready && -f /kind-ready ]] || exit 1
echo node
touch /node-ready
