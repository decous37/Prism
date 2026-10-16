#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -x .venv-build/bin/python ]]; then
  PYTHON="${PRISM_PYTHON:-.venv-build/bin/python}"
else
  PYTHON="${PRISM_PYTHON:-.venv/bin/python}"
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "请先创建虚拟环境并安装 requirements-build.txt（见 README.md）。" >&2
  exit 1
fi
"$PYTHON" -c 'import sysconfig; assert sysconfig.get_config_var("PYTHONFRAMEWORK"), "py2app 打包需要 framework Python，请先运行 ./scripts/bootstrap.sh"'
if [[ "$(uname -m)" != arm64 ]]; then
  echo "请在 Apple Silicon Mac 上构建。" >&2
  exit 1
fi
./scripts/build_native.sh
"$PYTHON" scripts/make_icon.py
"$PYTHON" -m unittest discover -s tests -v
mkdir -p dist
"$PYTHON" - <<'PY'
from pathlib import Path
import shutil
shutil.rmtree("dist/Prism.app", ignore_errors=True)
for path in Path("build").glob("bdist.*"):
    if path.is_dir():
        shutil.rmtree(path)
PY
"$PYTHON" setup.py py2app --arch arm64 > dist/build.log 2>&1 || {
  tail -60 dist/build.log >&2
  exit 1
}
APP="dist/Prism.app"
IDENTITY="${PRISM_SIGN_IDENTITY:--}"
# Re-sign nested Mach-O files before the enclosing bundle.
"$PYTHON" scripts/sign_app.py "$APP" "$IDENTITY"
codesign --verify --deep --strict --verbose=2 "$APP"
DMG="dist/Prism-macOS-arm64.dmg"
rm -f "$DMG"
if command -v create-dmg >/dev/null 2>&1; then
  create-dmg --volname Prism --volicon resources/Prism.icns \
    --window-pos 200 120 --window-size 560 360 --icon-size 100 \
    --icon Prism.app 150 160 --hide-extension Prism.app --app-drop-link 410 160 \
    "$DMG" "$APP"
else
  # Built-in fallback: the DMG still supports drag-to-Applications installation.
  STAGE="$(mktemp -d -t prism-dmg)"
  trap 'rm -rf "$STAGE"' EXIT
  ditto "$APP" "$STAGE/Prism.app"
  ln -s /Applications "$STAGE/Applications"
  hdiutil create -volname Prism -srcfolder "$STAGE" -format UDZO -ov "$DMG"
fi
hdiutil verify "$DMG"
(cd dist && shasum -a 256 Prism-macOS-arm64.dmg > Prism-macOS-arm64.dmg.sha256)
echo "已生成：$DMG"
if [[ "$IDENTITY" == - ]]; then
  echo "本地 ad-hoc 签名已完成；公开免警告分发需 Developer ID 签名和 Apple 公证。"
fi
