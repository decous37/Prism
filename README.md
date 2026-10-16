# Prism

**选中文字，按下快捷键，译文就在鼠标旁边。**

Prism 是一款轻巧的 Mac 划词翻译工具。读网页、看 PDF 或写代码时，选中一段文字，按 **⌘ ⌥ X** 就能翻译。译文显示在小浮窗里，看完点一下别处即可收起，继续手头的工作。

支持 Apple 系统翻译、Google 云端翻译和本机 Ollama 模型。默认使用系统翻译，下载语言资源后可离线使用。

[下载最新版](https://github.com/decous37/Prism/releases/latest) · [反馈问题](https://github.com/decous37/Prism/issues)

## 使用要求

- **macOS 15 或更高版本**
- **Apple Silicon 芯片**，如 M1、M2、M3、M4
- 需要授予辅助功能权限，用于读取其他应用中选中的文字

Release 安装包已包含 Python 和所需组件，下载安装后即可运行。Ollama 和模型需要另外安装，仅在使用 AI 翻译时需要。

## 安装

1. 从 [Releases](https://github.com/decous37/Prism/releases/latest) 下载 `Prism-macOS-arm64.dmg`。
2. 打开镜像，将 **Prism** 拖进 **Applications（应用程序）**。
3. 从应用程序中打开 Prism，在主页面点击 **重新授权**，按提示进入系统设置。
4. 在 **隐私与安全性 → 辅助功能** 中开启 **Prism**。

当前安装包采用本地签名，尚未经过 Apple 公证。首次打开时，macOS 可能会提示无法验证开发者。确认安装包来自本仓库的 Release 后，可在 **系统设置 → 隐私与安全性** 中选择“仍要打开”。企业或学校管理的 Mac 可能需要管理员允许安装。

## 日常使用

在其他应用中选中文字，按 **⌘ ⌥ X**，Prism 会自动识别语言：

| 选中的文字 | 翻译结果 |
| --- | --- |
| 中文 | 英文 |
| 英文、日文、法文、韩文等外语 | 简体中文 |

浮窗中只展示译文。你可以选择其中的文字，也可以使用底部按钮朗读、复制或修改设置。

| 操作 | 效果 |
| --- | --- |
| 点击复制按钮 | 复制译文，显示绿色“已复制” |
| 按 Enter | 复制译文，显示确认后收起浮窗 |
| 按 Esc、点击 × 或点击浮窗外 | 收起浮窗，Prism 继续运行 |
| 拖动卡片空白处或语言徽标 | 移动浮窗 |
| 点击齿轮 | 修改快捷键、翻译源和 AI 模型 |

**主页面与翻译浮窗是两个独立窗口。** 主页面可以通过 **⌘ Tab** 切换，打开时会显示在 Dock。关闭主页面后，Prism 留在后台，菜单栏和 Dock 都不会显示图标，翻译快捷键仍然可用。

需要调整授权或退出软件时，再次打开应用程序中的 Prism 即可回到主页面。点击 **退出 Prism** 会结束整个应用。

## 选择翻译源

### 系统原生

默认选项，使用 Apple Translation。首次使用某种语言时，按系统提示下载语言资源；下载完成后可离线翻译。选中的文字由系统翻译组件在本机处理。

可用语言组合取决于系统支持情况和已下载的资源。遇到暂不支持的语言组合，浮窗会给出提示，你可以手动切换翻译源。

### 轻量云端

通过 Google 翻译接口获取译文，免填 API Key。需要能够连接 Google 的网络，选中的文字会发送到 Google。网络状况和接口限流可能影响使用。

### AI 模型

默认连接本机 **Ollama**，使用 `qwen2.5:7b`。先安装 [Ollama](https://ollama.com)，再下载模型：

```sh
ollama pull qwen2.5:7b
```

在 Prism 中选择 **AI 模型**，点击 **启动模型**。Prism 会启动本机 Ollama 服务并加载已经下载的模型，准备完成后显示“模型已就绪”。也可以填写自己安装的其他模型名称。

首次加载模型需要一些时间，速度取决于模型大小和 Mac 的可用内存。模型由 Ollama 管理，关闭 Prism 后可能继续驻留一段时间。

AI 译文质量取决于所选模型。本机 `qwen2.5:7b` 在中文译日语、韩语的样例中出现过原文残留和额外解释。日常使用可以先选系统原生翻译。

## 常见问题

### 已经开启辅助功能，为什么还提示权限未生效？

本地签名的应用在升级或重新打包后，旧版本的授权记录可能失效。打开 Prism 主页面，点击 **重新授权**。应用会清理自身的旧记录、重启并重新发起申请，然后请你在系统设置中开启 Prism。

主页面每两秒读取一次系统实际返回的权限状态。开启成功后，状态会更新为“已授权”。

如果列表里没有 Prism，点击辅助功能列表下方的 **＋**，选择 `/Applications/Prism.app`。请始终运行应用程序中的这一份，避免同时打开构建目录里的副本。

### 快捷键没有反应怎么办？

先确认 Prism 仍在运行，并检查主页面中的权限状态。快捷键可以在主页面或浮窗设置中重新录制；如果与其他软件冲突，换一组组合键即可。

没有选中文字时，快捷键会打开提示浮窗。遇到某个应用无法读取选区，可以换一段文字重试，并在 Issue 中附上应用名称和版本。

### 支持哪些语言？

应用自动将中文译成英文，将其他语言译成简体中文。系统原生和轻量云端已用固定样例检查中英双向，以及日语、法语、韩语分别与中文、英文的双向翻译，各 14 个方向均返回了预期语言的译文。

完整结果见 [语言测试](docs/language-tests.md)。其中部分方向通过直接调用翻译引擎检查，当前界面仍按前面的自动规则选择目标语言。

## 数据与设置

Prism 的语言识别在本机完成。系统原生翻译和本机 Ollama 使用本地组件；选择轻量云端或远程 AI 服务时，选中文字会发送到相应服务。

读取选区时，Prism 优先使用辅助功能接口。部分应用需要借助复制操作取词，Prism 会先备份剪贴板并在读取后恢复；如果你随后主动复制了新内容，会保留你的新内容。

- 配置文件：`~/.prism_config.json`
- 日志文件：`~/Library/Logs/Prism/prism.log`

日志用于排查运行问题，不记录选中文字、译文或 API Key。

## 开发与构建

项目使用 **Python + PyObjC + pywebview**，界面由 HTML/CSS 编写。Apple Translation 通过一个小型 Swift 组件调用，构建需要 **Xcode Command Line Tools**，无需完整的 Xcode.app。

在 Apple Silicon Mac 上准备环境：

```sh
git clone https://github.com/decous37/Prism.git
cd Prism

xcode-select --install
brew install python@3.13
./scripts/bootstrap.sh
```

运行源码：

```sh
.venv-build/bin/python main.py
```

构建应用和 DMG：

```sh
./build_dmg.sh
```

输出文件位于 `dist/`：

- `Prism.app`：可独立运行的应用
- `Prism-macOS-arm64.dmg`：拖拽安装镜像
- `Prism-macOS-arm64.dmg.sha256`：安装包校验值

安装 `create-dmg` 后可生成带拖拽布局的镜像；未安装时会使用 macOS 自带工具打包。构建环境需要 Homebrew 或 python.org 提供的 **framework Python 3.12/3.13**。已有环境可以通过 `PRISM_BOOTSTRAP_PYTHON` 或 `PRISM_PYTHON` 指定，详见构建脚本。

运行测试（前端检查需要 Node.js）：

```sh
.venv-build/bin/python -m unittest discover -s tests -v
node tests/frontend.cjs
node tests/main_frontend.cjs
```

代码入口：

| 文件 | 职责 |
| --- | --- |
| `main.py` | 窗口、应用生命周期和前后端通信 |
| `ui.html` / `main.html` | 翻译浮窗与独立主页面 |
| `macos.py` / `hotkey.py` / `keyboard.py` | 选区读取、剪贴板、全局快捷键和按键处理 |
| `translator.py` / `ai_models.py` | 翻译请求、语言识别和 Ollama 启动 |
| `native/PrismTranslate.swift` | Apple Translation 组件 |
| `settings.py` / `geometry.py` | 配置保存和浮窗定位 |

远程 AI 接入、自定义签名及公证步骤见 [开发说明](docs/development.md)。

## 反馈

欢迎在 [Issues](https://github.com/decous37/Prism/issues) 提交问题或建议。反馈时请附上 macOS 版本、芯片型号、翻译源，以及能复现问题的操作步骤。涉及翻译内容时，可用一段公开的示例文字代替私人内容。
