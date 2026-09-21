---
name: bilibili-video-downloader
description: "B站（bilibili）视频下载工具，支持通过BV号/视频URL下载最高1080P高清MP4视频。自动打开浏览器扫码获取登录Cookie，调用B站官方API获取DASH流地址，下载音视频分离流后用ffmpeg合并为完整MP4。当用户要求下载B站视频、保存B站视频、批量下载B站课程/合集视频，或提供B站视频链接要求下载时使用。支持Windows/macOS/Linux。"
---

# B站视频下载器

## 概述

全自动B站视频下载：自动打开浏览器让用户扫码登录 → 自动获取Cookie → 调用API获取1080P直链 → 下载音视频流 → ffmpeg合并为MP4。**用户不需要手动复制Cookie，不需要打开DevTools。**

## 核心工作流程

### 第一步：确认输入

从用户输入中提取BV号。支持：
- 纯BV号：`BV1QgG36EERX`
- 完整URL：`https://www.bilibili.com/video/BV1QgG36EERX/...`
- 带参数的分享链接

用正则 `BV[a-zA-Z0-9]{10}` 提取。

确认用户要下载的视频列表和清晰度需求（1080P需要登录Cookie，480P匿名即可）。

### 第二步：获取登录Cookie（1080P必需）

**优先自动获取，不要让用户手动去DevTools复制。**

> **命令里的 `python` 需按平台替换**：Windows 用 `python`，macOS / Linux 用 `python3`（多数发行版不提供 `python` 命令）。

#### 方案A：自动获取Cookie（首选）

运行本Skill自带的Cookie获取脚本：

```bash
python scripts/get_cookies.py --output cookies/bilibili.txt
```

脚本会自动：
1. 打开浏览器到B站登录页
2. 用户扫码或输入账号密码登录
3. 自动检测登录成功（检测到SESSDATA）
4. 自动保存所有Cookie到文件

用户只需要在弹出的浏览器里扫码登录即可，**不需要打开DevTools，不需要复制任何东西**。

首次使用需安装依赖（如果脚本报错）：
```bash
pip install playwright
playwright install chromium

# 仅 Linux 需要，补齐 Chromium 的系统依赖（需 root）
sudo playwright install-deps chromium
```

如果chromium有问题，可以指定用系统Chrome或Edge：
```bash
python scripts/get_cookies.py --browser chrome    # 用Chrome
python scripts/get_cookies.py --browser msedge    # 用Edge（Windows / macOS）
```

> **无桌面环境（纯命令行服务器）跑不了方案A**——脚本需要弹出可见的浏览器窗口供扫码。这类环境直接用方案C取一次Cookie。

#### 方案B：如果已有Cookie文件

如果用户之前已经保存过Cookie，直接传给下载脚本即可：
```bash
python scripts/bilibili_downloader.py "<BV号>" --cookie-file cookies/bilibili.txt
```

#### 方案C：手动获取（仅在自动获取失败时）

只有在无法安装Playwright、无法弹出浏览器等情况下，才让用户手动操作：
1. 浏览器打开 bilibili.com 并登录
2. F12 → Application → Cookies → `https://www.bilibili.com`
3. 复制 SESSDATA、bili_jct、DedeUserID、DedeUserID__ckMd5 的值

> SESSDATA是HttpOnly的，`document.cookie`读不到，必须从Application面板复制。

### 第三步：执行下载

```bash
python scripts/bilibili_downloader.py "<BV号或URL>" \
  --output-dir <输出目录> \
  --quality 80 \
  --cookie-file <cookie文件路径>
```

参数：
- `--quality 80`：1080P（默认）。可选 64=720P, 32=480P
- `--cookie-file`：Cookie文件路径
- `--cookie`：直接传Cookie字符串
- `--output-dir`：输出目录，默认 `./downloads`

脚本自动完成：获取视频信息 → 获取DASH直链 → 下载视频流 → 下载音频流 → ffmpeg合并 → 验证文件。

### 第四步：批量下载

多个视频逐个下载，**每个视频间隔2-3秒**，避免触发B站-412风控。

### 第五步：交付

下载完成后交付MP4文件路径。文件名为视频标题。

---

## 关键注意事项

1. **优先自动获取Cookie**：不要让用户手动去DevTools复制SESSDATA。用 `get_cookies.py` 一键自动获取。
2. **SESSDATA是HttpOnly**：JS的 `document.cookie` 读不到它，必须通过Playwright/Selenium/CDP等浏览器自动化框架的 `context.cookies()` 或 `Network.getAllCookies` 获取。
3. **直链有时效**：playurl返回的URL约6小时过期，拿到后尽快下载。
4. **Referer必须带**：下载视频CDN文件时，请求头必须有 `Referer: https://www.bilibili.com`，否则403。
5. **H.264优先**：视频流选 `avc1` 编码而非 `hvc1`（H.265），兼容性更好。
6. **风控-412**：批量下载时间隔2-3秒，不要高频请求。
7. **大会员视频**：4K/1080P60等需要大会员，普通登录最高1080P。
8. **多分P视频**：每个P有独立cid，从 `data.pages[]` 中获取。

---

## 底层原理（需要手动实现时参考）

### 1. 获取视频信息
```
GET https://api.bilibili.com/x/web-interface/view?bvid={BV号}
```
提取 `cid`、`title`、`duration`。

### 2. 获取1080P直链
```
GET https://api.bilibili.com/x/player/playurl
    ?bvid={BV号}&cid={cid}&qn=80&fnval=4048&fourk=1
```
请求头带Cookie（SESSDATA等），否则最高480P。

返回 `data.dash.video[]` 选 `id=80` 且 `codecs` 以 `avc1` 开头的；`data.dash.audio[]` 选 `bandwidth` 最大的。

### 3. 下载音视频流
分别GET两个流URL，请求头带 `Referer: https://www.bilibili.com`。

### 4. ffmpeg合并
```bash
ffmpeg -y -i video.m4s -i audio.m4s -c copy output.mp4
```

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `scripts/get_cookies.py` | 自动获取Cookie（打开浏览器扫码，自动保存） |
| `scripts/bilibili_downloader.py` | 下载视频主脚本 |
| `references/api_reference.md` | B站API详细文档（参数、错误码、排查） |

需要了解完整API参数、错误码、故障排查时，读取：
- [references/api_reference.md](references/api_reference.md)
