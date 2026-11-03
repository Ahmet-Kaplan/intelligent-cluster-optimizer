#!/bin/bash
# Wall-clock-anchored memory pattern: usage in each 10-min segment depends only on (pattern, seed, segment),
# so every arm sees the same demand and a pod restart resumes the pattern where the clock is.
# Usage: pattern.sh PATTERN SEED            (level only: LEVEL_ONLY=1 pattern.sh PATTERN SEED EPOCH_SECONDS)
P=$1; SEED=$2
hash() { local x=$(( $1 + 1 )); echo $(( (x * x * 7919 + x * 104729 + SEED * 40503 + 12345) % 1000003 )); }
level() { # $1 = segment index
  local s=$(( $1 + SEED * 7 )) b=$(( $1 / 3 ))
  case $P in
    steady)     echo 300 ;;
    cycle-1h)   [ $(( (s / 3) % 2 )) -eq 0 ] && echo 150 || echo 450 ;;
    cycle-6h)   local v=(100 180 260 340 420 500 420 340 260 180 100 100); echo ${v[$(( (s / 3) % 12 ))]} ;;
    spike)      if [ $(( $(hash $b) % 4 )) -eq 0 ] && [ $(( $1 % 3 )) -eq 2 ]; then echo 600; else echo 200; fi ;;
    regime)     [ $(( (s / 48) % 2 )) -eq 0 ] && echo 200 || echo 450 ;;
    leak-reset) echo $(( 100 + 20 * (s % 26) )) ;;
    noisy)      echo $(( 150 + $(hash $1) % 301 )) ;;
  esac
}
if [ -n "$LEVEL_ONLY" ]; then level $(( $3 / 600 )); exit; fi
while true; do
  now=$(date +%s)
  stress-ng --vm 1 --vm-bytes "$(level $((now / 600)))M" --vm-hang 0 --timeout "$(( 600 - now % 600 ))s" >/dev/null 2>&1
done
