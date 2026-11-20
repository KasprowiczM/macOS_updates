#!/bin/sh
# SUDO_ASKPASS helper for update runs: never supplies a password.
# With it, a cold sudo timestamp in a child script or inside Homebrew fails at
# once instead of asking for a typed password in the middle of a run.
exit 1
