#!/bin/sh
echo legacy-boot
echo boot >> /legacy-count
touch /legacy-ready
exec sleep 600
