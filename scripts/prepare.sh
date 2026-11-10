#!/usr/bin/env bash
set -euo pipefail
KIT_DIR=$(cd "$(dirname "$0")/.." && pwd)
source "$KIT_DIR/sources.lock.env"
BUILD_DIR="$KIT_DIR/.work/fanchmwrt"
mkdir -p "$KIT_DIR/.work" "$KIT_DIR/artifacts"
if [[ -e "$BUILD_DIR" ]]; then
  echo "Build directory already exists: $BUILD_DIR. Preserve it for debugging; use a fresh kit for a new build." >&2
  exit 1
fi
git init -q "$BUILD_DIR"
git -C "$BUILD_DIR" remote add origin "$FANCHMWRT_URL"
git -C "$BUILD_DIR" fetch --depth 1 origin "$FANCHMWRT_COMMIT"
git -C "$BUILD_DIR" checkout --detach FETCH_HEAD
[[ "$(git -C "$BUILD_DIR" rev-parse HEAD)" == "$FANCHMWRT_COMMIT" ]]
cd "$BUILD_DIR"
git apply --check "$KIT_DIR/patches/0001-ra74-backport.patch"
git apply "$KIT_DIR/patches/0001-ra74-backport.patch"
python3 - "$FANCHMWRT_PACKAGES_COMMIT" "$ISTORE_COMMIT" <<'PY'
from pathlib import Path
import sys
p = Path('feeds.conf.default')
s = p.read_text()
old = 'src-git fanchmwrt https://github.com/fanchmwrt/fanchmwrt-packages.git'
assert s.splitlines().count(old) == 1, 'Unexpected fanchmwrt feed definition'
s = s.replace(old, old + '^' + sys.argv[1])
assert not any(line.startswith('src-git istore ') for line in s.splitlines())
s += '\nsrc-git istore https://github.com/istoreos/istore.git^' + sys.argv[2] + '\n'
p.write_text(s)
PY
./scripts/feeds update -a
git -C feeds/luci apply --check "$KIT_DIR/patches/0002-luci-weechat-provider.patch"
git -C feeds/luci apply "$KIT_DIR/patches/0002-luci-weechat-provider.patch"
./scripts/feeds install -a
cp "$KIT_DIR/configs/ra74.config" .config
make defconfig 2>&1 | tee "$KIT_DIR/artifacts/defconfig.log"
python3 - "$KIT_DIR/artifacts/defconfig.log" <<'PY'
from pathlib import Path
import sys
if 'recursive dependency detected!' in Path(sys.argv[1]).read_text():
    raise SystemExit('Kconfig dependency cycle; do not continue with this configuration')
PY
python3 "$KIT_DIR/scripts/verify.py" config "$BUILD_DIR"
cp .config "$KIT_DIR/artifacts/resolved.config"
./scripts/diffconfig.sh > "$KIT_DIR/artifacts/diffconfig"
cp feeds.conf.default "$KIT_DIR/artifacts/feeds.conf.locked"
cp "$KIT_DIR/sources.lock.env" "$KIT_DIR/artifacts/"
{
  git rev-parse HEAD
  for feed_dir in feeds/*; do
    if [[ -d "$feed_dir/.git" || -f "$feed_dir/.git" ]]; then
      printf '%s ' "$feed_dir"
      git -C "$feed_dir" rev-parse HEAD
    fi
  done
} > "$KIT_DIR/artifacts/source-revisions.txt"
echo 'Configuration verified. No firmware has been built or flashed yet.'
