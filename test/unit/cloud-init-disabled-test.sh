#!/bin/bash
#
# The live ISO must ship /etc/cloud/cloud-init.disabled.
#
# The autoinstall drive carries the cloud-init NoCloud label `cidata`, and the Arch releng
# profile this ISO is seeded from ships cloud-init. ds-identify therefore finds a datasource
# it was never meant to serve, writes a fallback DHCP config for the T2's unconnected
# internal USB NIC, and systemd-networkd-wait-online spends its whole 120 s timeout on it --
# in front of getty@tty1, because cloud-init-network orders itself Before=systemd-user-sessions.
# Measured 2026-09-19: autologin at 129.4 s for an 85-93 s install.
#
# This file is the switch that keeps that out. It is one empty-by-contract marker, so the
# only thing worth testing is that it is still there after a merge from upstream.

set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
MARKER="$ROOT/configs/airootfs/etc/cloud/cloud-init.disabled"

if [[ ! -f $MARKER ]]; then
  printf 'not ok - the live ISO ships /etc/cloud/cloud-init.disabled\n' >&2
  printf '  missing: %s\n' "${MARKER#"$ROOT"/}" >&2
  exit 1
fi
printf 'ok - the live ISO ships /etc/cloud/cloud-init.disabled\n'

# cloud-init tests for the path and ignores the contents, so anything readable is valid --
# but a marker nobody can explain is a marker the next merge deletes.
if ! grep -q 'cidata' "$MARKER"; then
  printf 'not ok - the marker says why it is there\n' >&2
  exit 1
fi
printf 'ok - the marker says why it is there\n'
