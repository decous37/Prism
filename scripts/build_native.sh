#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -m)" != arm64 ]]; then
  echo "Prism 需要在 Apple Silicon Mac 上构建。" >&2
  exit 1
fi
# An embedded Info.plist gives Translation a stable identity without a second
# application bundle that LaunchServices could put in the application launcher.
xcrun swiftc native/TranslationService.swift -parse-as-library -O \
  -target arm64-apple-macosx15.0 -framework AppKit -framework SwiftUI -framework Translation \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker native/translation-info.plist \
  -o native/prism-translation
codesign --force --sign - --identifier app.prism.translator.translation-service native/prism-translation
echo "系统翻译组件已构建。"
