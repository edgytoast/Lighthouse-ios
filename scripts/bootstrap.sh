#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR="$ROOT/vendor/Lighthouse"

LH_REPO="https://github.com/HarbourMasters/Lighthouse.git"
LH_PIN="29b5fdb76d208b127f1b23089d1b23b63987af50"
LUS_PIN="da6daf1a50a5e46d6641408d52227e31e85e46df"
TORCH_PIN="c63fa0780a16642d73b7710b89e10f7c4ba0c332"

die() { printf '\033[31mFATAL:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

if [ ! -d "$VENDOR/.git" ]; then
  info "Cloning $LH_REPO -> vendor/Lighthouse"
  mkdir -p "$ROOT/vendor"
  git clone --recursive "$LH_REPO" "$VENDOR"
fi

info "Pinning to D0 commits"
git -C "$VENDOR" fetch --all --tags --quiet
git -C "$VENDOR" checkout --quiet "$LH_PIN"
git -C "$VENDOR" submodule update --init --recursive --quiet

assert_pin() {
  local label="$1" dir="$2" want="$3" got
  got="$(git -C "$dir" rev-parse HEAD)"
  [ "$got" = "$want" ] || die "$label pin mismatch: want $want, got $got"
  printf '    %-12s %s\n' "$label" "$got"
}
assert_pin "Lighthouse"   "$VENDOR"                 "$LH_PIN"
assert_pin "libultraship" "$VENDOR/libultraship"    "$LUS_PIN"
assert_pin "Torch"        "$VENDOR/Torch"           "$TORCH_PIN"

DIRTY="$(git -C "$VENDOR" status --porcelain --untracked-files=no)"
if [ -n "$DIRTY" ]; then
  shopt -s nullglob
  series=("$ROOT"/overlay/patches/[0-9][0-9][0-9][0-9]-*.patch)
  if [ ${#series[@]} -eq 0 ]; then
    printf '%s\n' "$DIRTY" >&2
    die "vendor has modified tracked files but overlay/patches is empty — hand edits never happen (program rule 1)"
  fi
  info "vendor is modified; verifying the changes are exactly the overlay"
  for ((i=${#series[@]}-1; i>=0; i--)); do
    p="${series[i]}"
    if ! patch -p1 -R --force --fuzz=0 --dry-run -d "$VENDOR" < "$p" > /dev/null 2>&1; then
      die "overlay patch $(basename "$p") does not reverse — vendor has been hand-edited (program rule 1)"
    fi
  done
  info "    all ${#series[@]} patches reverse cleanly — vendor is pristine + overlay"
else
  info "vendor/ is pinned and pristine (no overlay applied)."
fi
