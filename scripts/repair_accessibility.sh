#!/bin/bash
set -euo pipefail
APP="/Applications/Prism.app"
if [[ ! -d "$APP" ]]; then
  echo "请先将 Prism 安装到 /Applications。" >&2
  exit 1
fi
# Stop only Prism at the installed path, so TCC sees a fresh process and code signature.
"$APP/Contents/MacOS/python" - <<'PY'
import os, signal, subprocess, time
executable = '/Applications/Prism.app/Contents/MacOS/Prism'
lines = subprocess.check_output(['ps', '-axo', 'pid=,comm='], text=True, encoding='utf-8').splitlines()
for line in lines:
    pid, _, command = line.strip().partition(' ')
    if command.strip() != executable:
        continue
    pid = int(pid)
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(.1)
    else:
        raise SystemExit('请从主页面退出 Prism 后重新运行此脚本。')
PY
/usr/bin/tccutil reset Accessibility app.prism.translator
/usr/bin/open "$APP" --args --request-accessibility
echo "已清除 Prism 旧授权并重新申请，请在系统设置中开启 Prism。"
