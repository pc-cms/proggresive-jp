#!/bin/sh
set -eu
: "${PROGRESSIVE_URL:?Set a trusted HTTPS server URL}"
profile_dir=${PROGRESSIVE_PROFILE_DIR:-"$HOME/.config/premier-progressive"}
command -v flock >/dev/null 2>&1 || { printf '%s\n' 'Install util-linux (flock) before starting the kiosk.' >&2; exit 1; }
umask 077
mkdir -p "$profile_dir"
# Desktop autostart and a manual launch must not each run a restart loop.
# Lock the persistent profile, not the URL: a second URL still shares Chrome.
exec 9>"$profile_dir/.kiosk-launcher.lock"
if ! flock -n 9; then
  printf '%s\n' 'Premier Progressive kiosk is already running for this profile.' >&2
  exit 0
fi
browser_pid=
numlock_watchdog=
cleanup() {
  trap '' HUP INT TERM
  if [ -n "$browser_pid" ]; then
    kill "$browser_pid" 2>/dev/null || true
    wait "$browser_pid" 2>/dev/null || true
  fi
  if [ -n "$numlock_watchdog" ]; then
    kill "$numlock_watchdog" 2>/dev/null || true
    wait "$numlock_watchdog" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 0' HUP INT TERM
numlockx on
# X11 watchdog: maintain Num Lock through normal operation, not only startup.
launcher_pid=$$
(while kill -0 "$launcher_pid" 2>/dev/null; do numlockx on; sleep 2; done) 9>&- &
numlock_watchdog=$!
xset s off
xset -dpms
xset s noblank
# Use a dedicated X11 kiosk user/session with no second browser profile.
while :; do
  numlockx on
  chromium --kiosk --no-first-run --disable-session-crashed-bubble --user-data-dir="$profile_dir" "$PROGRESSIVE_URL" &
  browser_pid=$!
  wait "$browser_pid" || true
  browser_pid=
  sleep 2
done
