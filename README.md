# B站视频下载 Skill

一个 Agent Skill：给一个 BV 号或视频链接，就能下载 B 站视频的最高 1080P MP4。

**全自动流程**：打开浏览器扫码登录 → 自动抓取 Cookie → 调用官方 API 拿 DASH 直链 → 下载音视频分离流 → ffmpeg 无损合并为 MP4。**不需要手动复制 Cookie，不需要打开 DevTools。**

---

## 特性

- **扫码登录，全自动取 Cookie** — 弹出浏览器让你扫码，脚本轮询检测到 `SESSDATA` 后自动保存，全程无手动复制
- **1080P 真高清** — 带登录 Cookie 请求 `qn=80`，匿名状态下 B 站最高只给 720P
- **DASH 流分离下载 + ffmpeg 无损合并** — `-c copy`，不重新编码，秒级完成，画质零损失
- **H.264 优先** — 自动选 `avc1` 而非 `hvc1`（H.265），兼容性更好
- **多级自动降级** — 1080P 不可用自动退 720P、480P；主 CDN 失败自动切备用 CDN
- **合并失败自动兜底** — `-c copy` 失败时回退到 `libx264` 重编码
- **成品自校验** — 合并后用 ffprobe 校验分辨率、编码、时长
- **批量下载** — 逐集下载，自动间隔规避 B 站 `-412` 风控

---

## 适用系统

| 系统 | 下载功能 | 自动获取 Cookie | 验证状态 |
|------|:---:|:---:|------|
| **Windows 10 / 11** | ✅ | ✅ | **实机验证通过**（含中文路径、1080P 全流程） |
| **macOS** | ✅ | ✅ | 代码层面无平台依赖，未实机验证 |
| **Linux（带桌面环境）** | ✅ | ✅ | 代码层面无平台依赖，未实机验证 |
| **Linux（无桌面的服务器）** | ✅ | ❌ | 代码层面无平台依赖，未实机验证 |

**几点必须说清楚的：**

- 上表只有 **Windows 一行是实测过的**。macOS 和 Linux 的结论来自逐行代码审查（无硬编码路径、无 `shell=True`、无盘符、无 Windows API 调用），**不是跑出来的**——我手上没有 macOS / Linux 机器可测。实际使用如遇问题欢迎开 Issue。
- **无桌面的 Linux 服务器有个硬限制**：`get_cookies.py` 要弹出可见的浏览器窗口供你扫码，纯命令行环境跑不了。这类环境下可以手动取一次 Cookie（见[方案 C](#方案-c手动获取仅在自动获取失败时)），之后 `bilibili_downloader.py` 照常可用。
- **Linux 装 Playwright 需要补系统依赖**，只跑 `playwright install chromium` 常因缺库失败。需要：

  ```bash
  sudo playwright install-deps chromium
  ```

---

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python | 3.7+（`sys.stdout.reconfigure` 需要 3.7；开发环境为 3.13） |
| ffmpeg | **必需**。合并音视频流 |
| requests | **必需**。HTTP 请求 |
| playwright | 可选，但强烈建议。自动获取 Cookie 用 |

> **Windows 下命令用 `python`，macOS / Linux 下用 `python3`。** 本文档统一写 `python`，非 Windows 平台请自行替换。

### 安装依赖

```bash
pip install requests playwright
playwright install chromium

# 仅 Linux 需要：补齐 Chromium 的系统依赖
sudo playwright install-deps chromium
```

**安装 ffmpeg：**

```bash
# Windows
winget install Gyan.FFmpeg

# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```

装完确认可用：

```bash
ffmpeg -version
```

---

## 安装

这是一个 Agent Skill，遵循 `SKILL.md` 约定（YAML frontmatter 中声明 `name` 与 `description`）。

### 方式一：让 Agent 自己装（推荐）

**把下面这个地址直接发给你的 Agent，让它自己完成安装：**

```
https://github.com/1221730273/bilibili-video-downloader
```

Agent 拿到后自行 clone 到它的 skills 目录即可。也可以直接给这条命令：

```bash
git clone https://github.com/1221730273/bilibili-video-downloader.git
```

### 方式二：手动 Clone

```bash
git clone https://github.com/1221730273/bilibili-video-downloader.git
```

克隆后把整个目录放进你的 Agent 的 skills 目录（约定路径形如 `~/.<agent>/skills/bilibili-video-downloader`，具体见你所使用的 Agent 文档）。装好后对 Agent 说「下载这个 B 站视频 + 链接」即可触发。

### 方式三：只当脚本用

不装在 Agent 里也行，clone 后直接跑，见下节。

---

## 使用

### 1. 获取登录 Cookie（1080P 必需）

```bash
python scripts/get_cookies.py --output cookies/bilibili.txt
```

脚本会打开浏览器停在 B 站登录页，你扫码或输密码登录，检测到 `SESSDATA` 后自动保存。Cookie 同时写入两个文件：

- `cookies/bilibili.txt` — `key=value; key2=value2` 一行式，供下载脚本读取
- `cookies/bilibili.json` — 完整 Cookie 数组备份

Chromium 有问题时可改用系统浏览器：

```bash
python scripts/get_cookies.py --browser chrome    # 用 Chrome
python scripts/get_cookies.py --browser msedge    # 用 Edge（Windows / macOS）
```

### 2. 下载视频

```bash
python scripts/bilibili_downloader.py "BV1QgG36EERX" \
  --output-dir ./downloads \
  --quality 80 \
  --cookie-file cookies/bilibili.txt
```

支持直接传完整链接（会自动提取 BV 号）：

```bash
python scripts/bilibili_downloader.py "https://www.bilibili.com/video/BV1QgG36EERX/" \
  --cookie-file cookies/bilibili.txt
```

### 参数说明

| 参数 | 默认 | 说明 |
|------|------|------|
| `--output-dir` | `./downloads` | 输出目录，文件名为视频标题 |
| `--quality` | `80` | 清晰度：`80`=1080P、`64`=720P、`32`=480P |
| `--cookie-file` | — | Cookie 文件路径 |
| `--cookie` | — | 直接传 Cookie 字符串（与 `--cookie-file` 二选一） |
| `--keep-temp` | 关 | 保留临时的 `.m4s` 分片文件 |

Cookie 还可以通过环境变量 `BILI_COOKIE` 传入，优先级：`--cookie` > `--cookie-file` > `BILI_COOKIE`。

### 批量下载

逐个视频调用即可，**每个之间间隔 2-3 秒**，避免高频请求触发 B 站风控：

```bash
for bv in BV1QgG36EERX BV1xx411c7mD BV1Abc123dEf; do
  python scripts/bilibili_downloader.py "$bv" --cookie-file cookies/bilibili.txt
  sleep 3
done
```

---

## 工作原理

B 站的高清视频走 DASH 协议，音视频是**两条独立的流**，必须分别下载再合并——这也是必须有 ffmpeg 的原因。

```
① GET /x/web-interface/view?bvid={BV}          → 拿 cid、标题、时长
② GET /x/player/playurl?bvid={BV}&cid={cid}
        &qn=80&fnval=4048&fourk=1               → 拿 DASH 直链（需 Cookie）
③ 分别 GET 视频流(avc1) + 音频流(码率最高)     → 需带 Referer，否则 403
④ ffmpeg -c copy 合并                          → 无损封装为 MP4
⑤ ffprobe 校验                                 → 分辨率/编码/时长
```

关键点：

- **`fnval=4048`** 才返回 DASH 格式，否则是低清 FLV
- **直链约 6 小时过期**，拿到后要尽快下载
- **下载 CDN 文件必须带 `Referer: https://www.bilibili.com`**，否则 403
- **`SESSDATA` 是 HttpOnly**，JS 的 `document.cookie` 读不到，必须通过 Playwright 的 `context.cookies()` 获取——这就是为什么要用浏览器自动化而不是纯 HTTP
- 匿名状态下 API 返回 `durl`（单个 MP4 直链）而非 `dash`，脚本会自动识别并走直下分支，无需 ffmpeg 合并

更完整的 API 参数、返回字段、错误码见 [`references/api_reference.md`](references/api_reference.md)。

---

## 平台差异处理

下面这些是已经处理掉的平台相关细节，列出来便于排查问题：

| 平台 | 问题 | 处理方式 |
|------|------|------|
| Windows | 控制台默认 GBK，脚本的 emoji 输出会抛 `UnicodeEncodeError` 直接中断 | 启动时强制把 stdout/stderr 切到 UTF-8（非 UTF-8 环境才触发，Unix 下自动跳过） |
| Windows | `subprocess` 默认按 locale 用 GBK 解码 ffmpeg 输出，含非 ASCII 字节时抛 `UnicodeDecodeError` | 所有子进程调用显式指定 `encoding="utf-8", errors="replace"` |
| 全平台 | 临时文件目录写死 | 用 `tempfile.gettempdir()`，自动适配各系统 |
| Windows | 标题含 `: * ? " < >` 等字符会导致建文件失败 | `sanitize_filename()` 统一过滤非法字符 |
| Linux | 只有 `python3`，没有 `python` 命令 | 文档已注明差异 |

**已知的边角情况（未处理，影响极小）：**

- `sanitize_filename()` 未处理 Windows 保留设备名（`CON`、`NUL`、`COM1` 等）和结尾的 `.` / 空格。B 站视频标题几乎不会命中，真遇到手工改个文件名即可。
- Linux 无桌面环境无法跑 `get_cookies.py`，见 [适用系统](#适用系统)。

---

## 常见问题

**Q：报 `python: command not found`？**
macOS / Linux 上换成 `python3`。

**Q：下载只有 720P，不是 1080P？**
Cookie 没生效。确认 `cookies/bilibili.txt` 里有 `SESSDATA`，且下载时传了 `--cookie-file`。日志里 `实际清晰度: 1080P` 才是真的拿到了。

**Q：报 403？**
下载 CDN 文件必须带 `Referer: https://www.bilibili.com`。本仓库的脚本已内置，若你自行实现了下载逻辑记得加上。

**Q：报 `-412` / `-352`？**
触发了风控，脚本会自动等待 5 秒重试。批量下载时间隔 2-3 秒，降低频率，等一段时间再试。

**Q：报 `-101`？**
登录态失效，Cookie 过期了。重新跑一次 `get_cookies.py`。

**Q：4K / 1080P60 下不了？**
这些属于大会员画质，普通登录账号最高 1080P。脚本已按普通账号优化。

**Q：多分P视频怎么下？**
每个 P 有独立的 `cid`，在 `data.pages[]` 里。当前脚本一次处理一个 cid，多分P 需要逐个调用。

**Q：Windows 上报 `UnicodeEncodeError: 'gbk' codec can't encode...`？**
脚本已做 UTF-8 强制切换，理论上不会出现。若仍出现，说明你用的是旧版本，更新到最新即可。

---

## ⚠️ 免责声明

本项目**仅供个人学习、研究与技术交流**，用于学习和备份你**有权访问**的内容。

- 请勿用于下载、传播或商业利用**受版权保护**的内容
- 请遵守 [B 站用户协议](https://www.bilibili.com/protocol/) 及相关法律法规
- 下载的内容版权归原 UP 主及平台所有，请勿二次上传或分发
- **请勿将本项目用于任何商业用途**

使用本工具产生的一切后果由使用者自行承担。

---

## 🔐 安全提醒

`cookies/` 目录下的文件包含 **`SESSDATA`**——那是你 B 站账号的**登录凭证，等同账号钥匙**。

- 本仓库的 `.gitignore` 已排除 `cookies/`，**请勿**用 `git add -f` 强行提交
- 一旦凭证进入 git 历史，即使后续删除也会永久留存（公开仓库 = 已泄露）
- 若怀疑泄露，立刻到 B 站「账号安全」里**退出所有设备**使 `SESSDATA` 失效

---

## 贡献

欢迎提 PR 或 Issue，尤其是：

- **macOS / Linux 的实机验证结果**（目前只有 Windows 经过实机确认）
- 无桌面 Linux 环境下的 Cookie 获取方案
- 多分P 批量下载支持
- Windows 保留文件名等边角情况的处理
