# WereadExport


本项目基于 [WeReadScan](https://github.com/Algebra-FUN/WeReadScan/tree/master) 改造， 通过 Chrome 和 Selenium 将微信读书中可正常阅读的内容导出为 Markdown 或 PDF。本项目是命令行工具，不提供本地 Web 服务。

## 环境准备

需要安装 uv 和 Google Chrome。项目使用 Python 3.12，uv 会根据 `.python-version` 和 `uv.lock` 创建虚拟环境并安装依赖。

进入项目目录并安装依赖：

```bash
cd WereadExport
uv sync --locked
```

项目名称为 **WereadExport**，Python 包名为 `weread_export`，命令名为 `weread-export`。
以下命令均在项目根目录运行。也可以使用等价入口 `uv run python -m weread_export`。

首次启动时，Selenium 会自动管理 ChromeDriver，需要联网下载匹配的驱动。

## 快速使用

### 检查运行环境

```bash
uv run weread-export --check
```

检查 Python 依赖、Chrome、WebDriver 和微信读书首页访问。检查通过不代表整本书导出已验证。

### 打开微信读书

```bash
uv run weread-export
```

打开可见的 Chrome 窗口后，程序会自动检查登录状态；未登录时打开微信扫码弹窗，
在浏览器中扫码并在手机上确认即可。登录成功后，控制台会明确提示成功并保持窗口打开。
关闭该窗口或按 Ctrl+C 即可退出。

登录和导出共用 `.browser-profile/`，登录状态有效期内无需重复扫码。
请先关闭登录窗口，再运行导出命令，不要同时运行多个进程，以免浏览器配置目录被占用。

控制台日志包含时间、浏览器启动、登录状态检查、点击登录、二维码加载、扫码等待、登录成功或失败。
等待扫码时每 10 秒输出一次进度；可用以下命令查看更详细的项目日志：

```bash
uv run weread-export --verbose
```

如需延长扫码等待时间：

```bash
uv run weread-export --login-wait 300
```

### 导出 Markdown

将下方占位链接替换为浏览器地址栏中的实际书籍阅读链接：

```bash
uv run weread-export "https://weread.qq.com/web/reader/b09326b0813aba103g0139e6" --format markdown
```

程序会检查保存的登录状态；未登录时显示微信登录二维码，默认等待 180 秒。
登录后从目录首项开始读取，保存至：

```text
output/书名.md
```

指定目录并延长扫码等待时间：

```bash
uv run weread-export "https://weread.qq.com/web/reader/书籍ID" \
  --format markdown \
  --output ./exports \
  --login-wait 300
```

Markdown 使用 UTF-8 编码，保留章节标题、段落、列表、表格和图片。
正文图片会自动下载到本地，无需额外参数；Markdown 使用相对路径引用，离线也可查看。
纯图片中的文字不会进行 OCR。具体用法及文件迁移方式见下方“本地图片与文件迁移”。

Markdown 命令默认从目录首项开始，避免微信读书恢复上次阅读位置导致漏掉前面的内容。
如需从当前阅读位置向后导出，添加 `--from-current`。

### 本地图片与文件迁移

以《八宅明镜》为例，以下命令会同时导出正文并保存原图：

```bash
uv run weread-export "https://weread.qq.com/web/reader/08a326b0813ab95cag012762" --format markdown
```

默认目录结构如下。图片文件名由内容哈希生成，扩展名保留原始图片格式：

```text
output/
├── 八宅明镜.md
└── assets/
    └── 八宅明镜/
        ├── 图片内容哈希.jpg
        └── 另一张图片内容哈希.png
```

使用 `--output ./exports` 时，Markdown 和图片会一起改为保存到 `exports/`：

```bash
uv run weread-export "https://weread.qq.com/web/reader/08a326b0813ab95cag012762" \
  --format markdown \
  --output ./exports
```

对应路径为 `exports/八宅明镜.md` 和 `exports/assets/八宅明镜/`。
Markdown 中的引用形如 `assets/书名/图片内容哈希.jpg`；中文和空格可能以 URL 编码显示，
这是正常的相对路径，不需要手动解码或修改。

移动、备份或分享时，请保持文件的相对位置：

- 最简单的方式是复制或压缩整个 `output/`（或自定义输出目录），在其他设备解压后打开 Markdown。
- 只分享一本书时，将它的 `.md` 文件与对应的 `assets/书名/` 放入同一个文件夹，保持下面的结构；无需包含其他书籍的图片。
- 只移动 `.md`、重命名图片文件或修改 `assets/书名/` 的目录名，都会导致图片引用失效；如需修改这些路径，必须同步修改 Markdown 中的图片引用。
- 导入笔记软件时，确认它会同时导入图片附件并保留或转换相对链接；仅粘贴 Markdown 文本不会带上本地图片。

```text
分享文件夹/
├── 八宅明镜.md
└── assets/
    └── 八宅明镜/
        ├── 图片内容哈希.jpg
        └── 另一张图片内容哈希.png
```

图片按内容去重并保留原始格式；日志会显示保存路径和文件大小。
下载暂时失败会重试；若图片无法下载或返回的内容不是有效图片，导出会停止并保留
`书名.partial.md` 和已下载的图片，不会把缺图文件标记为完成，也不会覆盖已有正式文件。
查看或移动 partial 文件时，也需要同时保留旁边的 `assets/书名/`。

### 导出 PDF

默认格式为 PDF，以下两种命令等价：

```bash
uv run weread-export "https://weread.qq.com/web/reader/书籍ID"
uv run weread-export "https://weread.qq.com/web/reader/书籍ID" --format pdf
```

默认保存至 `output/书名.pdf`，完成后尝试使用系统默认应用打开。PDF 通过页面截图生成。

### 不登录试读

只验证无需登录即可阅读的内容，并限制 Markdown 翻页数量：

```bash
uv run weread-export "https://weread.qq.com/web/reader/书籍ID" \
  --format markdown \
  --no-login \
  --max-pages 10
```

`--no-login` 不会取得额外阅读权限。达到页数上限且尚未确认书籍结束时，命令会以失败状态退出，并保留已读取的部分内容。

## 命令参数

```bash
uv run weread-export --help
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `book_url` | 无 | `https://weread.qq.com/web/reader/` 开头的阅读链接；不传时打开浏览器，Markdown 导出时必填 |
| `--format {pdf,markdown}` | `pdf` | 导出格式 |
| `--output 路径` | `output` | 输出目录，相对路径以当前工作目录为准 |
| `--login-wait 秒数` | `180` | 二维码展示后的扫码等待秒数，必须大于 0 |
| `--no-login` | 关闭 | 跳过扫码登录 |
| `--max-pages 数量` | `10000` | Markdown 翻页上限，必须大于 0，不影响 PDF |
| `--from-current` | 关闭 | Markdown 从当前阅读位置开始；默认从目录首项开始 |
| `--check` | 关闭 | 检查依赖、浏览器和首页连接后退出 |
| `--verbose` | 关闭 | 显示项目调试日志，不输出登录凭证 |

## Markdown 中断与输出文件

读取过程中会保存 `output/书名.partial.md`，开头注明导出尚未完成。只有检测到书籍结束标记后，才会将其替换为正式的 `书名.md`。

达到页数上限、阅读权限受限、正文读取超时或翻页失败时，命令会报错并注明卡住的阶段；如已读取到内容，会保留 partial 文件，不覆盖已有正式文件。重新运行默认从目录首项开始，不支持自动断点续传。成功导出会覆盖同名正式文件。

翻页判断同时检查页面 DOM 和 Canvas 画面，兼容只更新画布像素的阅读页。
微信读书页面结构变化仍可能影响登录、翻页和结束标记识别。
已使用登录状态验证《阳宅三要》：从目录首项读取至“全书完”，核对全部 10 个正文目录项。
《八宅明镜》已验证正文与图片一同导出，90 张本地图片均通过文件完整性与相对路径检查。

## Python 调用

```python
from selenium.webdriver import Chrome, ChromeOptions
from weread_export import WeRead

book_url = "https://weread.qq.com/web/reader/书籍ID"
options = ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--disable-blink-features=AutomationControlled")

with Chrome(options=options) as driver:
    with WeRead(driver) as weread:
        weread.login(wait_turns=180)
        weread.scan2markdown(book_url, save_at="output", max_pages=10000, from_start=True)
        # 如需导出 PDF，改为：
        # weread.scan2pdf(book_url, save_at="output")
```

Markdown 方法会创建输出目录；Python API 的 `from_start` 默认为 `False`，如需整本导出请显式设为 `True`。
直接调用 `scan2pdf` 前需自行创建输出目录。

## 测试

运行文本转换测试：

```bash
uv run python -m unittest discover -s tests -v
```

同时运行 Chrome 浏览器测试（使用本地模拟阅读页，不访问微信账号）：

```bash
WEREAD_BROWSER_TESTS=1 uv run python -m unittest discover -s tests -v
```

## 本地文件

| 路径 | 用途 |
| --- | --- |
| `.venv/` | uv 创建的虚拟环境 |
| `.browser-profile/` | 登录和导出共用的浏览器数据，请勿提交或分享 |
| `output/` | 默认导出目录 |
| `output/assets/书名/` | Markdown 的本地图片，需与 Markdown 一同保留 |
| `wrs-temp/` | 登录二维码、PDF 截图等临时文件，正常退出上下文时清理 |

仅导出自己有权阅读的内容，用于个人学习；请勿传播未经授权的图书内容。
