#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PRISM_BOOTSTRAP_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  for candidate in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3; do
    if [[ -x "$candidate" ]]; then PYTHON="$candidate"; break; fi
  done
fi
if [[ -z "$PYTHON" ]]; then
  echo "请先安装 framework Python：brew install python@3.13" >&2
  exit 1
fi
"$PYTHON" -c 'import sysconfig; assert sysconfig.get_config_var("PYTHONFRAMEWORK"), "需要 framework Python（Homebrew 或 python.org 发行版）"'
"$PYTHON" -m venv .venv-build
.venv-build/bin/python -m pip install -r requirements-build.txt
./scripts/build_native.sh
echo "环境已准备好。运行：.venv-build/bin/python main.py；打包：./build_dmg.sh"
