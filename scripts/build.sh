#!/usr/bin/env bash
set -euo pipefail
KIT_DIR=$(cd "$(dirname "$0")/.." && pwd)
BUILD_DIR="$KIT_DIR/.work/fanchmwrt"
cd "$BUILD_DIR"
python3 "$KIT_DIR/scripts/verify.py" config "$BUILD_DIR"
make download -j4 V=s 2>&1 | tee "$KIT_DIR/artifacts/download.log"
# Two jobs limit peak memory. Do not hide failures behind an automatic retry.
make -j2 V=s 2>&1 | tee "$KIT_DIR/artifacts/build.log"
python3 "$KIT_DIR/scripts/verify.py" image "$BUILD_DIR" "$KIT_DIR/artifacts"
