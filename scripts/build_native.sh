#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != arm64 ]]; then
  echo "Prism 需要在 Apple Silicon Mac 上构建。" >&2
  exit 1
fi
HELPER="native/PrismTranslate.app/Contents"
mkdir -p "$HELPER/MacOS"
cat > "$HELPER/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>app.prism.translate</string>
<key>CFBundleName</key><string>Prism 系统翻译</string>
<key>CFBundleExecutable</key><string>PrismTranslate</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSUIElement</key><true/>
<key>LSMinimumSystemVersion</key><string>15.0</string>
</dict></plist>
PLIST
xcrun swiftc native/PrismTranslate.swift -parse-as-library -O \
  -target arm64-apple-macosx15.0 -framework AppKit -framework SwiftUI -framework Translation \
  -o "$HELPER/MacOS/PrismTranslate"
codesign --force --sign - --identifier app.prism.translate native/PrismTranslate.app
echo "系统翻译组件已构建。"
