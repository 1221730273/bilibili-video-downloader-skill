# B站API参考文档

本文档详细记录B站视频下载涉及的所有API接口、参数、返回结构和错误码。

---

## 目录

1. [视频信息API](#1-视频信息api)
2. [播放地址API](#2-播放地址api)
3. [清晰度代码对照](#3-清晰度代码对照)
4. [关键Cookie说明](#4-关键cookie说明)
5. [防盗链与签名机制](#5-防盗链与签名机制)
6. [错误码大全](#6-错误码大全)
7. [常见问题排查](#7-常见问题排查)

---

## 1. 视频信息API

### 接口

```
GET https://api.bilibili.com/x/web-interface/view?bvid={BV号}
```

### 请求头

| 头部 | 值 | 说明 |
|------|-----|------|
| User-Agent | 标准浏览器UA | 必须 |
| Referer | `https://www.bilibili.com` | 建议带 |
| Cookie | 可选 | 不需要登录也能访问公开视频 |

### 返回结构（关键字段）

```json
{
  "code": 0,
  "message": "0",
  "data": {
    "aid": 117019202623446,
    "bvid": "BV1QgG36EERX",
    "cid": 40497579913,
    "title": "视频标题",
    "desc": "视频简介",
    "duration": 2526,
    "owner": {
      "mid": 123456,
      "name": "UP主名称"
    },
    "pages": [
      {
        "cid": 40497579913,
        "page": 1,
        "part": "第1P标题",
        "duration": 2526
      }
    ]
  }
}
```

### 关键提取

- `cid`：**必须提取**，获取播放地址时需要
- `title`：用于命名输出文件
- `pages`：多分P视频时，每个P有自己的cid，按 `page` 索引选择

---

## 2. 播放地址API

### 接口

```
GET https://api.bilibili.com/x/player/playurl
```

### 请求参数

| 参数 | 值 | 说明 |
|------|-----|------|
| bvid | BV号 | 视频标识 |
| cid | 分P ID | 从视频信息API获取 |
| qn | 80 | 请求的清晰度代码 |
| fnval | 4048 | 返回DASH格式（音视频分离） |
| fourk | 1 | 允许请求4K |

### 请求头（重要！）

| 头部 | 是否必须 | 说明 |
|------|---------|------|
| Cookie | 1080P必须 | 需要SESSDATA等登录态Cookie |
| Referer | 建议带 | `https://www.bilibili.com` |
| User-Agent | 必须 | 标准浏览器UA |

### 返回结构（DASH格式）

```json
{
  "code": 0,
  "data": {
    "quality": 80,
    "format": "flv",
    "accept_quality": [80, 64, 32, 16],
    "accept_description": ["高清 1080P", "高清 720P", "清晰 480P", "流畅 360P"],
    "dash": {
      "video": [
        {
          "id": 80,
          "codecs": "avc1.640033",
          "baseUrl": "https://upos-xxx.bilivideo.com/.../xxx-1-30080.m4s?...",
          "backupUrl": ["https://upos-backup.bilivideo.com/..."],
          "bandwidth": 148754
        },
        {
          "id": 80,
          "codecs": "hvc1.1.6.L150.90",
          "baseUrl": "...",
          "bandwidth": 191981
        }
      ],
      "audio": [
        {
          "id": 30280,
          "codecs": "mp4a.40.2",
          "baseUrl": "https://upos-xxx.bilivideo.com/.../xxx-1-30280.m4s?...",
          "bandwidth": 115673
        }
      ]
    }
  }
}
```

### 流选择策略

**视频流选择优先级：**

1. `id == 80` 且 `codecs` 以 `avc1` 开头 → 1080P H.264（兼容性最好）
2. `id == 64` 且 `codecs` 以 `avc1` 开头 → 降级720P
3. `id == 32` 且 `codecs` 以 `avc1` 开头 → 降级480P
4. 兜底：取 `dash.video[0]`

**为什么优先avc1而不是hvc1？**
- `avc1` = H.264编码，所有设备和播放器都支持
- `hvc1` = H.265/HEVC编码，压缩率更高但部分设备不兼容
- 普通用户下载建议选H.264，兼容性优先

**音频流选择：**
- 选 `bandwidth` 最大的那条（最高音质）
- 通常id=30280是高品质，id=30232是中品质

---

## 3. 清晰度代码对照

| qn值 | 清晰度 | 登录要求 | 备注 |
|------|--------|---------|------|
| 127 | 8K Super | 大会员 | 极少视频支持 |
| 120 | 4K (2160P) | 大会员 | |
| 116 | 1080P60帧 | 大会员 | |
| 112 | 1080P+ | 大会员 | |
| **80** | **1080P** | **普通登录** | **普通用户最高可下载清晰度** |
| 64 | 720P | 普通登录 | |
| 32 | 480P | 不需要登录 | 匿名默认 |
| 16 | 360P | 不需要登录 | |

> **注意**：即使请求了qn=120(4K)，如果不是大会员，实际返回的quality仍然是80(1080P)。API会自动降级。

---

## 4. 关键Cookie说明

### 必须的Cookie（1080P需要）

| Cookie名 | 作用 | 获取方式 |
|----------|------|---------|
| `SESSDATA` | 登录态核心凭证 | **HttpOnly**，JS读不到，需从DevTools导出 |
| `bili_jct` | CSRF Token | DevTools Cookie面板 |
| `DedeUserID` | 用户UID（数字） | DevTools Cookie面板 |
| `DedeUserID__ckMd5` | UID校验值 | DevTools Cookie面板 |

### 建议带上的Cookie

| Cookie名 | 作用 |
|----------|------|
| `buvid3` | 设备指纹，风控关键 |
| `buvid4` | 设备指纹，风控关键 |
| `buvid_fp` | 设备指纹 |

### 如何获取Cookie

**方法一：自动获取（推荐，用本Skill自带脚本）**

运行 `scripts/get_cookies.py`，自动打开浏览器，用户扫码登录后自动保存Cookie：

> 命令里的 `python` 按平台替换：Windows 用 `python`，macOS / Linux 用 `python3`。

```bash
# 基本用法
python scripts/get_cookies.py --output bilibili_cookies.txt

# 如果chromium有问题，用系统Chrome或Edge
python scripts/get_cookies.py --browser chrome
python scripts/get_cookies.py --browser msedge
```

首次使用需安装：
```bash
pip install playwright
playwright install chromium

# 仅 Linux 需要（需 root）
sudo playwright install-deps chromium
```

用户只需要在弹出的浏览器里扫码登录，脚本会自动检测登录成功并保存所有Cookie（包括HttpOnly的SESSDATA）。

**方法二：手动DevTools（仅在自动获取失败时）**
1. 浏览器登录B站
2. 按F12 → **Application（应用）** → **Cookies** → `https://www.bilibili.com`
3. 复制上述Cookie的Value

> 注意：`SESSDATA` 是HttpOnly的，`document.cookie` 在JS中读不到，必须从Application面板或浏览器自动化框架获取。

---

## 5. 防盗链与签名机制

### 视频CDN防盗链

视频文件托管在 `upos-*.bilivideo.com`，下载时校验：

1. **Referer头**：必须是 `https://www.bilibili.com`
2. **URL签名参数**：playurl返回的URL自带签名，不能篡改

### URL签名参数说明

直链URL中包含的关键参数：

| 参数 | 作用 |
|------|------|
| `e` | 加密后的过期时间和权限 |
| `deadline` | 过期时间戳（Unix时间） |
| `upsig` | 签名 |
| `uparams` | 参与签名的参数列表 |
| `mid` | 用户UID |
| `buvid` | 设备指纹 |
| `trid` | 请求追踪ID |

### 有效期

- playurl返回的直链约 **6小时** 后过期
- 过期后需要重新调用playurl API获取新直链
- 不要缓存直链，每次下载前重新获取

### 备用CDN

每个流都有 `backupUrl` 数组，当主CDN返回403时，可以尝试备用地址。

---

## 6. 错误码大全

| code | 含义 | 处理方式 |
|------|------|---------|
| 0 | 成功 | - |
| -1 | 未登录 | 提供有效Cookie |
| -101 | 账号未登录 | Cookie过期，重新获取 |
| -352 | 账号未登录或风控 | 补充buvid3/buvid4，等待重试 |
| -403 | 访问权限不足 | 不是大会员不能下会员视频 |
| -404 | 无此项 | BV号错误或视频已删除 |
| -412 | 请求被拦截（风控） | 降低频率，等待10秒后重试 |
| 10003 | 视频不存在 | 检查BV号是否正确 |

---

## 7. 常见问题排查

### Q1: 返回的quality一直是32（480P），上不去1080P

**原因**：登录态Cookie不完整或SESSDATA无效。

**排查**：
1. 确认Cookie中包含 `SESSDATA`
2. 确认 `SESSDATA` 值完整（很长的一串，不要截断）
3. 在浏览器中打开B站，确认已登录
4. 重新导出Cookie

### Q2: 下载时返回403 Forbidden

**原因**：缺少Referer头。

**解决**：下载请求必须加：
```
Referer: https://www.bilibili.com
```

### Q3: API返回-412

**原因**：触发B站风控。

**解决**：
1. 降低请求频率（每个视频间隔2-3秒）
2. 确保带上完整的Cookie（特别是buvid3/buvid4）
3. 等待10-15秒后重试
4. 不要短时间内批量请求

### Q4: 多分P视频怎么下载指定P？

**方法**：在视频信息API返回的 `pages` 数组中找到对应P的 `cid`，然后用该cid调用playurl API。

```python
# pages[0] 是第1P，pages[1] 是第2P
target_cid = info['pages'][1]['cid']  # 第2P
play = client.get_play_url(bvid, target_cid)
```

### Q5: 下载的视频没有声音？

**原因**：只下载了视频流，没下载音频流。

**解决**：B站DASH格式音视频分离，必须同时下载视频流和音频流，然后用ffmpeg合并：
```bash
ffmpeg -i video.m4s -i audio.m4s -c copy output.mp4
```

### Q6: 能下载大会员视频吗？

**不能**。大会员专属视频（4K、1080P60等）需要大会员账号的登录态。普通登录只能下载1080P。即使提供大会员Cookie，也需要确认账号确实是大会员。

---

## 附：检查登录状态API

```
GET https://api.bilibili.com/x/web-interface/nav
```
返回中 `data.isLogin` 为 `true` 表示已登录。
