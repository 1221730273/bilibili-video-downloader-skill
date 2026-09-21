# B站视频下载 Skill

一个用于 [Claude Code](https://claude.com/claude-code) 的 Skill：给一个 BV 号或视频链接，就能下载 B 站视频的最高 1080P MP4。

**全自动流程**：打开浏览器扫码登录 → 自动抓取 Cookie → 调用官方 API 拿 DASH 直链 → 下载音视频分离流 → ffmpeg 无损合并为 MP4。**不需要手动复制 Cookie，不需要打开 DevTools。**

> 本项目基于一份来源未知的上游 Skill 整理修复而来（详见文末「来源与许可」）。本仓库的主要价值是**修掉了上游在 Windows 上跑不起来的一批 bug**，详见 [Windows 修复清单](#windows-修复清单)。

---

## 特性

- **扫码登录，全自动取 Cookie** — 弹出浏览器让你扫码，脚本轮询检测到 `SESSDATA` 后自动保存，全程无手动复制
- **1080P 真高清** — 带登录 Cookie 请求 `qn=80`，匿名状态下 B 站最高只给 720P
- **DASH 流分离下载 + ffmpeg 无损合并** — `-c copy`，不重新编码，秒级完成，画质零损失
- **H.264 优先** — 自动选 `avc1` 而非 `hvc1`（H.265），兼容性更好
- **失败自动降级** — `-c copy` 失败时自动回退到 `libx264` 重编码
- **成品自校验** — 合并后用 ffprobe 校验分辨率、编码、时长
- **单文件批量下载** — 逐集下载，自动间隔 2-3 秒规避 B 站 `-412` 风控

---

## 环境要求

| 依赖 | 说明 |
|------|------|
| Python | 3.8+（开发环境为 3.13） |
| ffmpeg | **必需**。合并音视频流 |
| requests | **必需**。HTTP 请求 |
| playwright | 可选，但强烈建议。自动获取 Cookie 用 |

### 安装依赖

```bash
pip install requests playwright
playwright install chromium
```

**安装 ffmpeg：**

```bash
# Windows
winget install Gyan.FFmpeg

# macOS
brew install ffmpeg

# Debian / Ubuntu
sudo apt install ffmpeg
```

装完确认可用：

```bash
ffmpeg -version
```

---

## 安装为 Claude Code Skill

把本仓库放到 Claude Code 的 skills 目录下：

```bash
# 项目级
git clone https://github.com/<你的用户名>/<仓库名>.git .claude/skills/bilibili-video-downloader

# 或用户级（全局可用）
git clone https://github.com/<你的用户名>/<仓库名>.git ~/.claude/skills/bilibili-video-downloader
```

之后在 Claude Code 里说「下载这个 B 站视频 + 链接」，或直接用 `/bilibili-video-downloader` 触发。

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
python scripts/get_cookies.py --browser msedge    # 用 Edge
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

更完整的 API 参数、返回字段、错误码见 [`references/api_reference.md`](references/api_reference.md)。

---

## Windows 修复清单

上游脚本只在 macOS/Linux 上验证过，尽管它宣称「支持 Windows/macOS/Linux」。以下问题在 Windows 上会导致**直接跑不起来**，本仓库已全部修复：

| # | 文件 | 问题 | 症状 |
|---|------|------|------|
| 1 | `bilibili_downloader.py` | 未重设 stdout 编码，中文 Windows 默认 GBK，脚本里的 emoji 输出会抛 `UnicodeEncodeError` | 一运行就崩，第一行都打不出来 |
| 2 | `bilibili_downloader.py` | 硬编码 `/tmp/` 临时目录 | 合并阶段找不到临时文件 |
| 3 | `bilibili_downloader.py` | 缺 ffmpeg 时的提示只给了 apt/brew | Windows 用户不知道怎么装 |
| 4 | `bilibili_downloader.py` | 文档字符串里的 `python3` | Windows 无 `python3` 命令 |
| 5 | `get_cookies.py` | 同 #1 的 emoji 编码问题 | 一运行就崩 |
| 6 | `get_cookies.py` | `output_path.replace(".txt", ".json")` 在路径不含 `.txt` 时两路径相同，txt 被 JSON 覆盖；且缺 `os.makedirs` | 推荐的 `--output cookies/bilibili.txt` 因目录不存在直接失败 |
| 7 | `SKILL.md` / `api_reference.md` | 文档里的 `python3` 命令 | Windows 用户照抄会失败 |
| 8 | `get_cookies.py` | 函数内一句多余的局部 `import json`，使 `json` 成为整个函数的局部名，前面保存 JSON 备份时 `json.dump` 抛 `UnboundLocalError` | **登录成功、txt 已写好之后才崩**，看着像失败其实 Cookie 已到手 |
| 9 | `bilibili_downloader.py` | `subprocess.run(..., text=True)` 未指定编码，Windows 按 GBK 解码 ffmpeg 输出 | 子线程抛 `UnicodeDecodeError` 刷一大段 traceback；**非致命**，合并不受影响 |

#8 是上游的全平台 bug（非 Windows 特有），但症状最迷惑；#9 只是噪音，不影响产物。

---

## 常见问题

**Q：下载只有 720P，不是 1080P？**
Cookie 没生效。确认 `cookies/bilibili.txt` 里有 `SESSDATA`，且下载时传了 `--cookie-file`。日志里 `实际清晰度: 1080P` 才是真的拿到了。

**Q：报 403？**
下载 CDN 文件必须带 `Referer: https://www.bilibili.com`。本仓库的脚本已内置，若你自行实现了下载逻辑记得加上。

**Q：报 `-412`？**
触发了风控。批量下载时间隔 2-3 秒，降低频率，等一段时间再试。

**Q：4K / 1080P60 下不了？**
这些属于大会员画质，普通登录账号最高 1080P。脚本已按普通账号优化。

**Q：多分P视频怎么下？**
每个 P 有独立的 `cid`，在 `data.pages[]` 里。当前脚本一次处理一个 cid，多分P 需要逐个调用。

**Q：`UnicodeEncodeError: 'gbk' codec can't encode...`？**
你用的还是未打补丁的上游版本。见上方 [Windows 修复清单](#windows-修复清单) #1、#5。

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

## 来源与许可

本仓库的 `scripts/` 与 `references/` 源自一份**来源不可考的上游 Skill**（未随附作者信息或许可证），本仓库在其基础上完成了 Windows 兼容性修复。

**因此本仓库未附加任何 LICENSE 文件**——在无法确认上游授权条款的情况下，不宜代为声明许可。若你是原作者或知晓上游出处，欢迎提 Issue 补充署名与许可信息。

本仓库新增的修复、文档为整理者所加，可自由参考。

---

## 贡献

欢迎提 PR 或 Issue，尤其是：

- 上游出处的线索（作者、原始仓库、许可证）
- 其他平台的兼容性修复
- 多分P 批量下载支持
