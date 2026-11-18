#!/bin/bash
# Remove files a deploy no longer ships, on the host that received it.
#
#   prune.sh candidates DIR MANIFEST          list untracked files in DIR (NUL-separated)
#   prune.sh apply DIR MANIFEST [IGNORED]     delete what the new MANIFEST dropped
#
# MANIFEST is the NUL-separated list of tracked paths of the revision being
# deployed. With a previous DIR/.deployed-files, exactly the paths that left
# the manifest are deleted. Without one, every file in DIR that is neither in
# the manifest nor listed in IGNORED (paths git ignores, decided where the
# repo is) is deleted. Generated state is never touched.

set -euo pipefail

die() { printf '[fail] %s\n' "$*" >&2; exit 1; }

protected() {
  case "$1" in
    .env|.deployed*|startup/files/output/*|build/certs/ssl/*|build/proxy/certs/ssl/*|volumes|volumes/*) return 0 ;;
  esac
  return 1
}

# Prints a NUL-separated list unchanged, refusing paths that leave DIR.
read_list() {
  local p
  while IFS= read -r -d '' p; do
    case "$p" in
      ''|/*|..|../*|*/..|*/../*) die "unsafe path in $1: $p" ;;
    esac
    printf '%s\0' "$p"
  done < "$1"
}

mode=${1:-}; dir=${2:-}; manifest=${3:-}; ignored=${4:-}
[ -d "$dir" ] || die "no such directory: $dir"
[ -f "$manifest" ] || die "no such manifest: $manifest"

# Validate up front: a die inside process substitution would not stop the script.
for list in "$manifest" "$dir/.deployed-files" ${ignored:+"$ignored"}; do
  if [ -f "$list" ]; then read_list "$list" >/dev/null; fi
done

declare -A keep=()
while IFS= read -r -d '' p; do keep[$p]=1; done < <(read_list "$manifest")

untracked() {
  local p
  while IFS= read -r -d '' p; do
    p=${p#./}
    [ -n "${keep[$p]:-}" ] && continue
    protected "$p" && continue
    printf '%s\0' "$p"
  done < <(cd "$dir" && find . \( -type f -o -type l \) -print0)
}

case "$mode" in
  candidates)
    untracked
    ;;
  apply)
    victims=()
    if [ -f "$dir/.deployed-files" ]; then
      while IFS= read -r -d '' p; do
        [ -n "${keep[$p]:-}" ] && continue
        protected "$p" && continue
        if [ -e "$dir/$p" ] || [ -L "$dir/$p" ]; then victims+=("$p"); fi
      done < <(read_list "$dir/.deployed-files")
    else
      [ -f "$ignored" ] || die "no previous manifest and no ignore list given"
      declare -A skip=()
      while IFS= read -r -d '' p; do skip[$p]=1; done < <(read_list "$ignored")
      while IFS= read -r -d '' p; do
        [ -n "${skip[$p]:-}" ] || victims+=("$p")
      done < <(untracked)
    fi
    for p in ${victims[@]+"${victims[@]}"}; do
      rm -f -- "$dir/$p"
      printf '  removed %s\n' "$p"
      d=$(dirname "$p")
      while [ "$d" != "." ] && rmdir -- "$dir/$d" 2>/dev/null; do
        printf '  removed %s/\n' "$d"
        d=$(dirname "$d")
      done
    done
    printf '  %s stale file(s) removed\n' "${#victims[@]}"
    ;;
  *) die "usage: prune.sh candidates|apply DIR MANIFEST [IGNORED]" ;;
esac
