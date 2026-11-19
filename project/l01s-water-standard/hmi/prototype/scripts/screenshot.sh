#!/usr/bin/env bash
# HMI 原型截图：Edge 无头 → hmi/docs/assets/screenshots/*.png
# 用法: bash hmi/prototype/scripts/screenshot.sh   （在项目根执行）
# 沿用工作区管线（参照 req-20261102 panama 原型）：
# 坑1：Edge 是 Windows 程序，路径必须用 cygpath -m 转 Windows 形式
# 坑2：每张图窗口尺寸不同（800x480 页 vs 2560x1164 合成大图），按行配置
set -euo pipefail
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
[ -f "$EDGE" ] || EDGE="/c/Program Files/Microsoft/Edge/Application/msedge.exe"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"            # hmi/
PAGES_WIN="$(cygpath -m "$ROOT/prototype/pages")"
OUT="$ROOT/docs/assets/screenshots"
OUT_WIN="$(cygpath -m "$OUT")"
mkdir -p "$OUT"
# src | out | w | h
SHOTS=(
  "overview.html|overview.png|800|480"
  "overview-sleep.html|overview-sleep.png|800|480"
  "params.html|params.png|800|480"
  "diagnostics.html|diagnostics.png|800|480"
  "contact-sheet.html|HMI-PREVIEW-V005.png|2560|1164"
)
for line in "${SHOTS[@]}"; do
  IFS='|' read -r src out w h <<< "$line"
  "$EDGE" --headless --disable-gpu --force-device-scale-factor=1 \
    --window-size="$w,$h" \
    --screenshot="$OUT_WIN/$out" "file:///$PAGES_WIN/$src" 2>/dev/null
  [ -s "$OUT/$out" ] || { echo "FAIL $out"; exit 1; }
  echo "OK $out ($w x $h)"
done
ls -la "$OUT"
