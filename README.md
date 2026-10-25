# PDF 文档双语翻译器：Windows GUI + CLI

输入 PDF，选择输出目录和中文／英文／双语／全部，选择 **TeX + PDF、仅 PPTX 或 TeX + PDF + PPTX** 输出组合。双语按条目和子项逐条对齐，**中文一行、英文紧随下一行**，长句会自然换行。输出语言“全部”同时生成中文、英文、双语三套；根据输出格式分别生成 6、3 或 9 个主要文件。程序先在本地解析；内容不完整或缺少目标语言时，需要 LLM 补全后才能输出。不会自动生成原貌版来替代合格的转换结果。

## Windows GUI

双击 **`dist/release/PDFBilingual.exe`**。exe 内含 Python、Tk、PDF 解析与 PPT 导出依赖，不需要安装 Python。生成 PDF 还需本机安装 MiKTeX 等提供的 `xelatex`。无需任何 `.cmd` 或 GUI 启动脚本。

主界面只有：

- 输入 PDF、浏览按钮。
- 输出目录、浏览按钮。
- 输出语言：中文、英文、双语、全部（中文＋英文＋双语）。
- 输出格式：TeX + PDF、仅 PPTX、TeX + PDF + PPTX。
- “配置 LLM…”按钮和“连接 LLM”复选框。
- “生成”“停止”按钮，以及一个处理日志窗口。

右上角可以切换中文／English 界面。界面语言独立于输出语言。

点击“生成”后：

1. 读取 PDF，提取本地文字、位置和图片。
2. 检查是否存在扫描页、公式／图形结构问题，或缺少所需译文。
3. 内容完整时，直接继续，本次不调用 LLM。简单的中英逐行交替原文可以直接对齐。
4. 内容不完整且未勾选“连接 LLM”时，停止并在日志中提示：启用 LLM，或通过 agent 的 CLI 继续处理。不会生成最终文件。
5. 已勾选时，自动连接配置的 LLM，补全并翻译所需页面，随后继续生成；不需要第二次点击。
6. 所选语言和输出格式全部生成成功后，才发布到选择的输出目录。LLM 只做一次双语补全，再复用内容生成三套版本。编译失败或模型仍无法确认内容时，不发布部分结果；之前已有的输出不因失败而覆盖。

日志显示当前步骤、本次是否无需 LLM、是否已经连上 LLM、各页处理进度和最终输出位置。

### LLM 配置

点击“配置 LLM…”填写 Base URL、模型名称和 API Key。支持 Chat Completions 兼容接口；模型须支持图片输入和 JSON 对象输出。Base URL 填接口根地址，例如 `https://api.openai.com/v1`，不包含 `/chat/completions`。

API Key 仅保存在当前进程内存，也可从 `OPENAI_API_KEY` 环境变量读取，不写配置文件。接口地址、模型、输出目录和界面语言可保存在 `dist/config/settings.json`。连接复选框默认关闭；只配置接口不会联网。

勾选连接后，仅在有待办页面时发送这些页面的文字和截图。每页完成后保存进度，失败后重新生成会继续处理剩余页面。停止在当前页结束后生效；API 请求最长等待 120 秒。真实模型返回不合格内容、断网或额度不足时，会停止并显示原因。

## CLI

独立 GUI 不需要 Python；从源码使用 CLI 时，需要 Python 3.11+。在最外层项目目录安装源码包：

```powershell
py -3 -m pip install -e ./repo
```

PPTX 将相邻插图与对应编号题目、说明和公式放在同一页：宽图置于文字下方，窄图使用左右布局；长内容在中英对照条目之间分页，相关图随说明保留，避免只有图片而没有题目的页面。关联依据 `content.json` 的块顺序（插图紧跟对应题目及说明），编辑中间数据时应保留这个顺序。

数学教材的 PPTX 可选用可编辑的 Office 公式：源码环境安装 `py -3 -m pip install -e "./repo[math]"`，并在本机安装 Microsoft Office。程序使用本机的 `MML2OMML.XSL` 将 LaTeX 转为 Office Math，不联网。未安装该可选依赖时使用普通文本公式。PDF 仍由 XeLaTeX 排版；内嵌的希腊字母、音标及中文词例使用相应字体。插图保留原图标注。

一次完成与 GUI 相同的流程：

```powershell
pdf2bilingual convert "dist/input/Statistics 1&2&3-stamped.pdf" --output "D:/my-output" --lang bi --format tex-pdf

# 仅生成中文、英文、双语三份 PPTX
pdf2bilingual convert "dist/input/Statistics 1&2&3-stamped.pdf" --output "D:/my-output" --lang all --format pptx

# 需要自动连接模型时显式开启；Key 从环境变量读取
pdf2bilingual convert "dist/input/Statistics 1&2&3-stamped.pdf" --output "D:/my-output" --lang bi --enable-model --base-url https://api.openai.com/v1 --model YOUR_VISION_MODEL
```

安装后也可使用 `python -m cli` 代替 `pdf2bilingual`；`pdf2bilingual-gui` 或 `python -m gui` 启动源码 GUI。从项目根目录直接运行源码时，用 `python repo/src/cli.py ...`。输出语言为 `zh`、`en`、`bi`、`all`；`--format tex-pdf` 生成 TeX + PDF，`--format pptx` 仅生成 PPTX，`--format all`（默认）生成全部三种格式。语言与格式独立组合，例如 `--lang all --format pptx` 生成 3 个 PPTX。仅导出 PPTX 不需要 XeLaTeX，也无需携带外部图片目录；TeX + PDF 则需要 XeLaTeX，且 TeX 必须连同引用图片保存。

### 没有 LLM API：交给 Codex 等 agent 运行 CLI

**没有 API Key 也可以处理扫描页和翻译。** 在能读取本地文件、查看图片并运行终端的 Codex 等 agent 中打开最外层项目目录，让 agent 使用自己的模型能力处理 CLI 导出的任务。本程序不再额外调用模型 API；不需要填写 API Key，也不需要在 GUI 中勾选“连接 LLM”。Agent 自身的模型访问和额度仍由所用 agent 提供。

GUI 在本地解析不完整时会停止。此时可以直接让 agent 接手已有的 `dist/work/<key>/`，无需重新手工准备 JSON 或截图。CLI 的具体流程如下（在最外层项目目录运行；使用 agent 当前可用的 Python）：

```powershell
# 默认项目名为输入文件名去掉特殊字符，例：Statistics_1_2_3-stamped
python repo/src/cli.py extract "dist/input/Statistics 1&2&3-stamped.pdf"
python repo/src/cli.py status Statistics_1_2_3-stamped --lang bi
python repo/src/cli.py export-task Statistics_1_2_3-stamped --lang bi

# Agent 读取 codex_task/PROMPT.txt、task.json 和指定页面图像，保存逐页 result.json
python repo/src/cli.py import-result Statistics_1_2_3-stamped "dist/work/Statistics_1_2_3-stamped/codex_task/result.json"
python repo/src/cli.py convert "dist/input/Statistics 1&2&3-stamped.pdf" --output "D:/my-output" --lang all
```

如果之前已在 GUI 或 CLI 中解析过，跳过 `extract`，直接 `status` 和 `export-task`。`status` 在有待办时返回退出码 2，表示需要补全，并非程序崩溃。目标为“全部”时，导出 `--lang bi`，补全一次双语后即可复用生成三套。

可以把下面的要求直接发给 agent：

```text
请在当前项目中处理 dist/input/Statistics 1&2&3-stamped.pdf，目标为中文、英文、双语全部版本。
我没有 LLM API，请不要使用 --enable-model 或调用外部模型 API。
请运行 repo/src/cli.py，复用已有解析结果；必要时先 extract。
用 export-task --lang bi 导出任务，读取 PROMPT.txt、task.json 和它指定的页面截图。
由你直接识别、翻译并逐条对齐，按任务格式保存 result.json；双语中文在前、英文在后。
用 import-result 校验并导入，再运行 convert --lang all --output dist/output。
支持分批处理；无法辨认的内容应保留为待办，不要猜测，也不要输出不完整成品。
```

导入后，处理结果会更新到 `content.json`，模型定位的插图由本地程序裁切并更新图片库。支持分批导入，原文、坐标始终保留。导入验证源文件指纹、页码、目标语言、双语子项数量和图片裁图范围，修改前会自动备份。

高级命令仍提供 `build`、`crop`、`assist` 等，见 `python repo/src/cli.py --help`。旧章节式 JSON 可用 `python repo/src/legacy.py <key>`。退出码：0 成功；1 参数／处理失败；2 内容不完整、需要继续处理。

## 数据和输出

最外层仅保留 `repo/`、`dist/`。**只有 `repo/` 进入版本控制并上传**，`dist/` 为本地数据与产物，位于 Git 仓库外。公开仓库为 [Tao-ingenieur/pdf2bilingual-desktop](https://github.com/Tao-ingenieur/pdf2bilingual-desktop)。

```text
项目根/
  repo/                              Git 仓库，仅源码和文档
    .git/
    .gitignore
    README.md
    pyproject.toml                   依赖、安装和命令入口
    src/
      paths.py                       统一路径管理
      cli.py                         CLI 入口
      legacy.py                      旧章节 JSON 构建入口
      pipeline/                      PDF 提取、LLM、裁图和文档生成
      gui/                           GUI 和中英文界面翻译
    packaging/                       PyInstaller 配置和打包脚本
    tests/                           自动测试
  dist/                              本地生成，不上传 Git
    release/PDFBilingual.exe          独立 Windows 程序
    input/                           原始 PDF
    work/<key>/content.json           原文、位置、状态和处理结果
    work/<key>/figures/               页面截图及裁图
    work/<key>/backups/               修改前备份
    work/<key>/builds/                未发布构建／失败诊断
    output/                          默认交付目录，可另选
    config/settings.json             本机设置，不含 API Key
    qa/                              验证样本和报告
    build/                           构建工具、环境、缓存和临时文件
```

最终文件命名为 `<key>_ZH/EN/BI.tex/.pdf/.pptx`，TeX 引用图片位于输出目录的 `figures/<key>_<语言>/`。移动 TeX 时要同时移动相应图片。exe 在 `dist/release/` 时会使用同一个 `dist/input`、`dist/work`、`dist/output`，不会创建 `release/dist`。移动项目时保留这层结构；单独移动 exe 到其他目录时，它会使用新目录下的 dist。可用 `PDFBILINGUAL_HOME` 指定最外层项目目录。

输出文件直接保存在所选目录，不额外生成 ZIP 压缩包。

从 GitHub 获取源码时，可保持相同布局：

```powershell
mkdir pdf2bilingual
cd pdf2bilingual
git clone https://github.com/Tao-ingenieur/pdf2bilingual-desktop.git repo
py -3 -m pip install -e ./repo
```

输入文件、exe、本机设置和构建环境不会随源码推送。Git 远程 `origin` 指向 GitHub 公开仓库。

本地完整性检查使用保守规则。表格、图片、数学结构无法可靠提取时会请求补全，不把简单文字抽取当作完整转换。图中的原始文字仍留在裁图内，图内翻译需要另外处理。

## 验证和重新打包

```powershell
python -m unittest discover -s repo/tests -v
python -m pip install -e "./repo[build]"
powershell -NoProfile -File repo/packaging/build-exe.ps1 -Python python
```

打包结果为 `dist/release/PDFBilingual.exe`。构建工具、PyInstaller 缓存、临时文件和测试临时目录统一放在 `dist/build/`，不需要分发。自测：

```powershell
./dist/release/PDFBilingual.exe --self-test --language en --report dist/qa/simple-exe.json
```

测试覆盖简化界面、中英切换、无 LLM 完成、缺失内容阻止输出、开启 LLM 自动继续、生成失败不覆盖旧文件、导入校验和图片裁切。API 回归测试使用模拟接口，不消耗额度。回归测试还覆盖输出格式组合、PPTX 不依赖 XeLaTeX、图文同页、图文无交叠及双语顺序。
