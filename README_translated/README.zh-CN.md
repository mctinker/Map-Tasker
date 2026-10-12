<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../documentation_images/maptasker_logo_dark.png">
    <img src="../documentation_images/maptasker_logo_light.png" alt="MapTasker">
  </picture>
</p>

<div align="center">

![PyPI](https://img.shields.io/pypi/v/maptasker)
![PyPI - Downloads](https://img.shields.io/pypi/dm/maptasker?color=green&label=downloads)
![Downloads](https://static.pepy.tech/personalized-badge/maptasker?period=total&units=international_system&left_color=grey&right_color=green&left_text=downloads)
![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fmctinker%2FMap-Tasker%2Frefs%2Fheads%2FMaster%2Fpyproject.toml)
![PyPI - License](https://img.shields.io/pypi/l/maptasker)
![](https://tokei.rs/b1/github/mctinker/Map-Tasker)
[![Sourcery](https://img.shields.io/badge/Sourcery-enabled-brightgreen)](https://sourcery.ai)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)

</div>

<p align="center">
  <b>Read this in:</b>
  <a href="../README.md">English</a> •
  <a href="README.zh-CN.md">简体中文</a> •
  <a href="README.es.md">Español</a> •
  <a href="README.hi.md">हिन्दी</a> •
  <a href="README.fr.md">Français</a> •
  <a href="README.ar.md">العربية</a> •
  <a href="README.de.md">Deutsch</a> •
  <a href="README.da.md">Dansk</a> •
  <a href="README.fi.md">Suomi</a> •
  <a href="README.ru.md">Русский</a> •
  <a href="README.ko.md">한국어</a> •
  <a href="README.ja.md">日本語</a>
</p>

---

# MapTasker

> 本翻译由机器翻译生成，如有出入，请以 [英文原版 README](../README.md) 为准。

## 在您的（Mac / Windows 11 / Linux）桌面浏览器中，基于 Tasker 的备份或导出的 XML 文件，显示/编辑/分析 Tasker 的 Project（项目）、Profile（配置文件）、Task（任务）和 Scene（场景）

配置地图（Configuration Map）...
![MapTasker 配置地图：以彩色缩进大纲形式展示的一个 Project、其 Profile 和 Task，每个 Task 下列出其编号的 Action 及设置](../documentation_images/intro.png)

图表地图（Diagram Map）...
![MapTasker 图表地图：以方框绘制的 Project 和 Profile，其下方是 Task，连线表示哪个 Task 调用哪个 Task，其中一条调用路径被高亮显示](../documentation_images/Introd.png)

[[更多示例]](<https://github.com/mctinker/Map-Tasker/wiki#sample-output>)

这是一个配合 [Tasker](https://tasker.joaoapps.com/) 使用的应用程序，旨在运行于网页浏览器中（参见[注 1](#1)）。

我发现自己的 Tasker Project/Profile/Task/Scene 变得越来越难以管理，而手机屏幕又太小，无法方便地浏览这些 Project、Profile、Task 和 Scene。于是我编写了一个 Python 程序，根据保存在本地桌面硬盘上的 Tasker 备份 XML 文件，在网页浏览器中生成整个配置的完整地图。

随着时间推移，我不断完善这个地图，加入了许多附加选项，包括编辑 Tasker 对象以及对 Tasker 配置进行深入分析的能力。

Tasker 的备份文件或其他 Tasker 导出的 XML 文件，既可以手动上传到您的 PC/Mac/Linux 电脑或云盘，也可以由本程序直接从您的 Android 设备获取（参见[注 2](#2)）。

## 功能特性

- 可自由选择输出详细程度，从概览摘要到非常详细的配置层级。
- 仅显示单个 Project、Profile 或 Task。
- 包含/排除 Profile 和 Task 的条件：State（状态）、Event（事件）等。
- 可选择直接流式输出，或通过对齐所有字段使输出更"美观"。
- 更改外观：选择"浅色"或"深色"模式。
- 使用您喜欢的等宽字体输出，并通过斜体、粗体、高亮和/或下划线来强调 Project、Profile 和 Task 的名称。
- 修改输出中各部分关联的颜色，以适应您的心情。
- 包含 TaskerNet 描述和/或 Tasker 偏好设置。
- 对于复杂的配置，可选择包含指向您的 Project、Profile、Task 和 Scene 的超链接目录。
- 显示整个 Tasker 配置的图表以及 Task Flow（任务流程图）。
- 命令行或图形界面。
- 使用导出的 XML，或直接从您的 Android 设备获取 XML 以生成配置地图。
- 将 Project、Profile、Task 和 Scene 发送回您 Android 设备上的 Tasker。
- 保存和恢复运行时设置。
- 识别包含过多"Action"的 Task，这些 Task 可能应该被拆分为多个 Task。
- AI 分析选项，可使用基于服务器的 ChatGPT/Claude/Gemini，或基于本地的 Llama（通过 Ollama）等受支持的模型，分析指定的 Project、Profile、Task 或 Scene。
- 在图形界面中直接显示结果：（配置）地图视图、树状视图和图表视图。
- 自动检测更新，并可选择安装新版本。
- 增强的搜索功能和结构化的"查找/替换"。
- 添加和编辑 Project、Profile、Task 和 Scene（参见[注 6](#6)）。
- 列出自指定日期以来的更改。
- 将 Project、Profile、Task 或 Scene 关联到其来源的 TaskerNet 分享，在作者发布新版本时收到通知，并逐项采纳其更改。
- 分析 Tasker XML 的健康状况，以及整个配置中众多变量的状态。
- 将某个 XML 文件与已加载的 XML 进行比较。

## 程序依赖

### - Python 3.11 或更高版本

### - Tasker 完整或部分 XML 文件：backup.xml 或其他 Tasker 导出的 XML 文件

&nbsp;&nbsp;&nbsp;系统会提示您在桌面上定位并选择由 Tasker 5 或 6 版本创建的、已导出的 XML 文件（例如 backup.xml）。您也可以选择直接从您的 Android 设备获取该文件（参见[注 2](#2)）。

### - AI 分析

&nbsp;&nbsp;&nbsp;如果使用基于服务器的分析，则需要有效的 API 密钥；如需进行本地分析，则需要安装 Ollama（参见[注 3](#3)）。


## 安装

本程序及其所有依赖项将占用约 230MB 的空间。建议将其安装在虚拟环境中（选项 2）。

- 在终端/命令提示符中输入以下任一命令以安装 MapTasker：

     ```python -m pip install maptasker -U```
                 ...或者...
     ```uv add maptasker```

- 要将其安装到虚拟环境中，请在终端/命令提示符中输入以下命令：

  通过 pip 安装...
  - `cd xxx`，其中 "xxx" 是您想要建立虚拟环境的目录。
  - `python -m venv venv`
  - 激活虚拟环境...
    MAC/Linux： `source {directory path to 'xxx'}/venv/bin/activate`
    Windows： `venv\Scripts\activate`
  - `pip install maptasker`

  ...或者...
  
  通过 uv 安装...
  - `cd xxx`，其中 "xxx" 是您想要建立虚拟环境的目录。
  - `uv venv`
  - 激活虚拟环境...
    MAC/Linux： `source {directory path to 'xxx'}/venv/bin/activate`
    Windows： `venv\Scripts\activate`
  - `uv pip install maptasker`

- AI 分析功能需要额外的库（OpenAI、Anthropic、Google 和 Ollama）。MapTasker 不会自动为您安装这些库；如果您需要它们，请改用带有 `ai` 附加选项的方式安装 MapTasker：

     ```python -m pip install "maptasker[ai]" -U```
                 ...或者...
     ```uv add "maptasker[ai]"```
  
## 使用方法

- 输入以下命令：

     ```maptasker```
     ...或者，如果您使用 uv 来管理虚拟环境...
     ```uv run maptasker```

### 命令行报告

Health Check（健康检查）、Compare（比较）、Changes Since（变更追踪）、Export（导出）以及文件夹监视（watch）均可在无窗口模式下运行，因此可以自动检查每晚的 Tasker 备份（通过 `cron`、任务计划程序、`launchd` 或 CI 作业触发）：

```
maptasker -healthcheck -file backup.xml                 # 检查某个备份中的问题
maptasker -compare older.xml newer.xml                  # 比较两个备份之间的差异
maptasker -changes_since week -file backup.xml          # 列出变更：today（今天）、week（本周）、month（本月）、all（全部）、某个日期，或 3d（3 天前）
maptasker -export map -format md -file backup.xml       # 将地图（或图表）导出为 md、json 或 pdf 格式
maptasker -watch ~/TaskerBackups                        # 将每个新备份记录到历史记录中
```

- **`-file`** 可接受一个备份文件，或一个文件夹（将使用其中最新的 `.xml` 文件）。 `-outdir` 用于选择文件写入的位置， `-save` 则会（像窗口模式一样）将报告另存为文件。
- **只有报告本身会写入标准输出（standard output）**；其他所有内容都写入标准错误（standard error），因此 `maptasker -healthcheck -file backup.xml > report.txt` 会得到一份干净的报告。
- **退出代码（Exit codes）** 可供脚本根据结果作出相应处理：

  | 代码 | 含义 |
  |---|---|
  | 0 | 已完成，且无需报告任何内容 |
  | 10 | 报告发现了问题：Health Check 错误（使用 `-fail_on warning` 以包含警告，使用 `-fail_on never` 以忽略警告），或存在差异 |
  | 11 | `-changes_since` 没有可供比较的更早配置（首次运行将开始建立历史记录） |
  | 1 | 程序错误 |
  | 2 | 无法写入文件（包括无法使用的 `-outdir` 文件夹），或无法生成输出 |
  | 3 | 该文件不是有效的 Tasker 备份 |
  | 5 | 未找到请求的单个 Project、Profile 或 Task（通过 `-project`、`-profile` 或 `-task` 指定） |
  | 6 | 未提供文件，或该文件/文件夹不存在 |
  | 7 | 选项无效，例如颜色设置错误、未知的 `-fail_on` 值，或将某个文件与其自身进行比较 |
  | 8 | 对运行 Tasker 服务器的 Android 设备的请求失败 |

- **历史记录。** 每次加载的备份都会被记录到配置历史记录中，这正是 `-changes_since` 所读取的数据。`-watch FOLDER` 会按文件日期记录出现在该 `FOLDER` 中的每一个新的、完整的备份，因此即使您某天没有打开 MapTasker，历史记录也会持续更新；`-watch FOLDER -once` 则只检查一次，适用于定时作业。历史记录保存在运行 MapTasker 所在目录下的 `MapTasker_Timeline` 文件夹中，因此定时作业应使用 `-history_dir` 指向与窗口模式所使用的相同文件夹。
- **其他内容不受影响。** 这些运行方式永远不会打开浏览器，也永远不会重写窗口模式所保留的设置。

## 程序输出

MapTasker 会在桌面和 Android 设备上生成多种输出文件。

有关 MapTasker 生成的输出的完整列表，请参阅[维基百科（wiki）](https://github.com/mctinker/Map-Tasker/wiki/Generated-Output)。


## 更多内容： [[运行时选项]](https://github.com/mctinker/Map-Tasker/wiki/Runtime-Options)&nbsp;&nbsp;&nbsp;[[运行时选项示例]](https://github.com/mctinker/Map-Tasker/wiki/Sample-Runtime-Options)&nbsp;&nbsp;&nbsp;[[示例输出]](https://github.com/mctinker/Map-Tasker/wiki#sample-output)

## 项目结构

以下是主要文件及其用途的简要概述：

- `maptasker/`：包含核心应用程序代码。
  - `maptasker/src/`：MapTasker 逻辑的主要 Python 源文件。
  - `maptasker/assets/`：应用程序使用的静态资源，如图标、图片和 JSON 数据。
  - `maptasker/locale`：用于翻译的语言文件。
- `documentation_images/`：本 README 及其他文档中使用的图片。
- `tools/`：开发过程中使用的工具。
- `tests/`：包含用于保证代码质量的测试脚本及相关文件。
- `maptasker/main.py`：`maptasker` 命令背后的入口点。若使用克隆下来的仓库，请运行 `python -m maptasker.main`。
- `LICENSE`：本项目的 MIT 许可证文件。
- `README.md`：本文件（英文原版）。
- `Changelog.md`：记录每个版本所做更改的日志。
- `pyproject.toml`：项目元数据及构建系统配置。

## 许可证

本项目基于 [MIT 许可证](../LICENSE) 授权。

MIT 许可证是起源于麻省理工学院（MIT）的一种宽松的自由软件许可证。作为一种宽松许可证，它对再利用的限制非常有限，因此具有很高的许可证兼容性。

简而言之，这意味着您可以自由地：

- **使用**：出于任何目的（商业或私人用途）使用本软件。
- **修改**：修改本软件。
- **分发**：分发原始或修改后的软件。
- **再授权**：对软件进行再授权。

您必须：

- **包含版权声明**：在软件的任何重要部分中包含原始版权声明及许可证本身。

本软件按"现状"提供，不附带任何形式的担保。完整许可证文本请参阅 [LICENSE](../LICENSE) 文件。

## 故障排除与常见问题（FAQ）

**问：在 Windows 的记事本（Notepad）中，`MapTasker_Map.txt` 图表看起来排列错乱。**

答：记事本可能无法正确处理此文件的间距。

建议使用其他文本编辑器，例如 Notepad++、VS Code 或 Typepad（并将其设置为 `.txt` 文件的默认程序）。请确保关闭"自动换行"并使用等宽字体。

**问：如何直接从我的 Android 设备获取 Tasker XML 文件？**

答：前提条件：

1 - 浏览器所在的电脑与 Android 设备需处于同一局域网内。

2 - 已在 Android 设备上安装并激活了 ['Http Server Example' Tasker 项目](https://shorturl.at/bwCD4)，且服务器正在运行。

更多详情请参阅本 README 的"注释"部分。

**问：对于中文、韩语或日语的名称，图表连接线会出现错位。**

答：这是图表绘制库中与这些语言的字体度量相关的一个已知问题。

**问：为什么某些 Task 的 Action 和 Profile 的 State/Event 无法进行编辑/添加？

答：在某些情况下，这些 Action、Event 或 State 所需的信息仅能在 Android 设备和/或 Tasker 本身中获得。如果允许编辑这些内容，将导致 Task 或 Profile 不完整，从而造成 Tasker 运行失败。

## 注释

"故障排除与常见问题"部分中提及的部分要点的详细信息，保留于此供进一步参考。

### 1
**Windows 11 相关说明：**

- 仅支持 Windows 11。更早版本的 Windows 均不受支持。
- 若 `MapTasker_Map.txt` 在记事本中显示有问题，请使用其他文本编辑器（如 Typepad）并将其设置为 `.txt` 文件的默认程序。

### 2
**从 Android 直接获取 XML：**

要直接获取 Tasker XML 文件：

- 请确保桌面设备和 Android 设备处于同一局域网内，并且 Tasker 正在运行。
- 必须在 Android 设备上安装并激活 ['Http Server Example' Tasker 项目](https://shorturl.at/bwCD4)，且服务器正在运行。请记得运行 "Update GD HTTP Info" 这个 Task，并在首次使用时在提示出现时输入您的 Google Drive ID。
- 获取之后，该 XML 文件会保存在您的桌面上，除非发生变更，否则不需要重复获取。

### 3
**AI 支持**

AI 分析功能仅在图形界面中可用。您只能针对单个 Project、Profile、Task 或 Scene 运行分析。支持基于服务器的 OpenAi（ChatGPT）、Gemini 和 Anthropic，以及基于本地的 Llama 模型。

基于 Llama 的模型通过 [Ollama](https://ollama.com/) 提供支持，您需要手动下载、安装并至少运行一次，以在您的桌面上建立该服务器。如果尚未加载相应的 Llama 模型，MapTasker 会为您动态加载。

支持 AI 功能的模块默认不会随 MapTasker 一起安装。相反，它们会在您首次使用特定的 AI 请求时被动态安装。这样一来，如果您不打算使用 AI 功能，就不会产生相应的额外开销。


## 应用程序编辑与分析注意事项
**MapTasker 编辑与分析注意事项**

详情请参阅[注意事项（Caveats）](https://github.com/mctinker/Map-Tasker/blob/Master/caveats.txt)文档。


## 待办事项列表（排列不分先后）

- [ ] 就绪状态检查（Readiness Check）

- [x] 支持更多插件

- [ ] 映射剩余的 Tasker 偏好设置

- [ ] Task Stepper（任务单步调试）：逐个 Action 地"空跑"模拟一个 Task，显示哪些 If、For 和 Goto 分支会被执行，以及每个变量的取值

- [ ] Live Run Monitor（实时运行监视器）：实时流式展示手机上触发的 Profile 和 Task，并在图表视图中高亮显示它们

- [ ] 针对两个备份相对于共同祖先的三方合并（Three-way merge），逐个冲突地解决，并可一步撤销

- [x] TaskerNet 更新追踪器：当您所使用分享的作者发布新版本时通知您，并提供更改的差异对比

- [ ] 个人代码片段库：保存可复用的 Action 序列、Task 和 Profile 模板，并带参数插入

- [ ] 地图中的通俗解释：由 AI 撰写、经过缓存且可编辑的每个 Profile 和 Task 的一行摘要

- [ ] 缺失资源检查器：验证您的 Action 所引用的文件、文件夹、图片、声音、Scene 和应用是否仍然存在

- [ ] 复杂度与趋势仪表盘：随时间追踪 Task 长度、嵌套层级、调用链深度以及发现的问题

- [ ] 文档站点导出：导出一组相互链接的 Markdown 或 HTML 页面，每个 Project、Profile、Task 和 Scene 各一页，并带有调用关系图

- [ ] 变量重命名与作用域助手：在所有使用处重命名变量，或将全局变量变为局部变量，均可作为一次操作撤销

## 隐私声明

除下文（网络流量）所列内容外，不会有任何信息通过网络被捕获并发送给本人或任何第三方。

如果您报告了一个错误，您很可能会被要求提供错误发生时的输出日志文件以及您的 XML 文件，这两者仅用于调试本程序，使用后会立即删除。

网络流量情况如下：

- 从您的 Android 设备直接获取 XML 时产生的本地局域网流量。
- 启动时每天一次，向 pypi.com 检查是否有新版本发布。
- 如果在图形界面中选择了"升级"，则会通过 pip 从 pypi.com 更新程序。
- 如果在图形界面中选择了"新功能介绍"（What's New），则会从 '<https://github.com/mctinker/Map-Tasker>' 读取 'Changelog.md' 文件。
- 使用任意 OpenAi 模型进行 AI 分析时，会访问 chatgpt.com。MapTasker 的输出将通过标准 API 调用发送至该服务器以进行分析。使用 Claude（Anthropic）和 Gemini（Google）时同理。
- 运行 AI 分析功能时，会从 '<https://ollama.com/library>' 加载新的及更新后的本地 AI 模型。
- 当点击 Task 的 Action 标签以及 TaskerNet 描述中通过 '<img src=https://...>' HTML 标签定义的图片和视频来源超链接时，将会访问这些链接。示例：imggur.com、Youtube、Dropbox、Google Drive 等。

## 贡献指南

欢迎贡献！以下是您可以为 MapTasker 做出贡献的一些方式：

**报告错误：**

- 如果您发现了错误，请在 [GitHub Issues 页面](https://github.com/mctinker/Map-Tasker/issues)上提交一个 issue。
- 请尽可能提供详细信息：
  - 重现该错误的步骤。
  - 预期行为与实际行为。
  - 您的操作系统及 Python 版本。
  - MapTasker 的版本。
  - 您的 Tasker XML 文件中相关的部分（如适用，并请确保不包含任何敏感信息）。
  - 如果使用 `-debug` 选项生成了 `maptasker.log` 文件，请附上该文件。

**提出改进建议：**

- 在 GitHub 上提交一个 issue，说明您的建议。
- 解释该使用场景，以及为什么这项改进会有益。

**提交 Pull Request：**

- 如果您想贡献代码：
    1. Fork（派生）该仓库。
    2. 为您的功能或错误修复创建一个新分支（例如 `feature/new-output-format` 或 `fix/xml-parsing-error`）。
    3. 进行您的更改。
    4. 确保您的代码符合 Black 代码风格（如徽章所示）。
    5. 如适用，请在 `tests/` 目录中为您的更改添加测试。
    6. 确保所有测试均通过。
    7. 向 `Master` 分支提交 pull request。

**编码风格：**

- 本项目使用 [Ruff](https://docs.astral.sh/ruff/formatter/) 进行代码格式化。请确保您的贡献已使用 Ruff 进行格式化。

感谢您为改进 MapTasker 所提供的帮助！

## 已知问题

- 对于中文、韩语或日语的名称，图表连接线会出现错位。
- 并非所有 Task 的 Action 和 Profile 的 State/Event 编辑都受支持，因为其中一些需要仅在 Android 设备上才能获得的信息。

## 贡献者

[Taskometer](https://github.com/Taskomater/Tasker-XML-Info)

[©Connor Talbot 2021，Clippy 作者](https://github.com/con-dog/clippy)

[Ollama](https://ollama.com/)、[OpenAi](https://openai.com/)、[Claude AI](https://claude.ai)、[Gemini AI](https://gemini.google.com/)

[NiceGui](https://nicegui.io/)

[!["Buy Me A Coffee"](../documentation_images/coffee.png)](https://www.buymeacoffee.com/mctinker)
