# 开发说明

日常使用和基本构建步骤见 [README](../README.md)。

## 运行环境

应用面向 macOS 15+、Apple Silicon。当前安装版在 macOS 26.4.1 上测试，macOS 15 的兼容路径已按对应部署目标编译，尚未在 macOS 15 实机测试。

`./scripts/bootstrap.sh` 会创建 `.venv-build`、安装依赖并编译 Swift 翻译组件。它会查找 Homebrew 和 python.org 的 framework Python；也可显式指定：

```sh
PRISM_BOOTSTRAP_PYTHON=/path/to/framework/python3 ./scripts/bootstrap.sh
PRISM_PYTHON=/path/to/venv/bin/python ./build_dmg.sh
```

uv 的独立 Python 可运行部分源码，但 py2app 打包需要 framework Python。

运行时可使用独立配置文件：

```sh
.venv-build/bin/python main.py --config /path/to/config.json
```

`--request-accessibility` 会在启动时发起辅助功能申请并打开系统设置。测试全局快捷键和授权时，建议使用安装到 `/Applications/Prism.app` 的完整应用。

## AI 服务配置

默认使用 `http://localhost:11434/v1/chat/completions`，模型为 `qwen2.5:7b`。退出 Prism 后，可编辑 `~/.prism_config.json` 中的 `ai_url`，填写其他 OpenAI 兼容服务的完整聊天补全地址。

需要认证的远程服务可通过 `PRISM_AI_API_KEY` 环境变量提供 Bearer 凭据。此变量需要由启动 Prism 的进程传入；从 Finder 启动时通常不会继承终端里的变量。凭据不会写入配置，也不会附加到默认的本地 Ollama 请求中。

“启动模型”只负责默认端口上的本机 Ollama，远程服务需要自行启动。

## 测试

```sh
.venv-build/bin/python -m unittest discover -s tests -v
node tests/frontend.cjs
node tests/main_frontend.cjs
```

Python 测试覆盖配置校验、翻译路由、异常处理、缓存、剪贴板恢复、快捷键、窗外点击、模型启动和独立窗口行为。剪贴板序列化测试使用专用测试剪贴板。

前端检查运行页面内的实际脚本，覆盖复制反馈、Enter、×、模型启动状态，以及主页面的设置保存、权限显示和收起/退出操作。

需要发起真实的多语言请求时运行：

```sh
.venv-build/bin/python scripts/check_languages.py
```

该脚本会调用三种翻译源，使用公开示例句，报告输出到本地 `artifacts/language-checks/`。系统可能提示下载缺少的语言资源；AI 测试需要已安装的 Ollama 和配置中的模型。[已保存的样例结果](language-tests.md) 可用于查看各方向的输出。

## 应用签名与公证

`./build_dmg.sh` 默认使用 ad-hoc 签名，适合本机测试。每次构建的代码哈希可能变化，替换应用后有时需要重新授权辅助功能。

要制作经 Apple 验证的公开安装包，需要自己的 Apple Developer ID 证书和公证凭据：

```sh
PRISM_SIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)' ./build_dmg.sh
xcrun notarytool submit dist/Prism-macOS-arm64.dmg --keychain-profile prism-notary --wait
xcrun stapler staple dist/Prism-macOS-arm64.dmg
(cd dist && shasum -a 256 Prism-macOS-arm64.dmg > Prism-macOS-arm64.dmg.sha256)
```

证书和公证配置由发布者保管，仓库不包含这些凭据。

## 权限排查

安装版主页面中的“重新授权”会清理 Prism 自身的旧 Accessibility 记录，重启后重新发起申请，最后由用户在系统设置中开启。

也可从项目目录运行：

```sh
./scripts/repair_accessibility.sh
```

该脚本仅针对 `/Applications/Prism.app`，会退出该应用、重置旧记录并重新打开授权页面。授权开关需要用户亲自操作。
