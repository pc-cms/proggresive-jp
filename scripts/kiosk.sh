#!/bin/sh
set -eu
: "${PROGRESSIVE_URL:?Set a trusted HTTPS server URL}"
numlockx on
# X11 watchdog: maintain Num Lock through normal operation, not only startup.
(while :; do numlockx on; sleep 2; done) &
numlock_watchdog=$!
trap 'kill "$numlock_watchdog" 2>/dev/null || true' EXIT HUP INT TERM
xset s off
xset -dpms
xset s noblank
# Use a dedicated X11 kiosk user/session with no second browser profile.
while :; do
  numlockx on
  chromium --kiosk --no-first-run --disable-session-crashed-bubble --user-data-dir="$HOME/.config/premier-progressive" "$PROGRESSIVE_URL" || true
  sleep 2
done
