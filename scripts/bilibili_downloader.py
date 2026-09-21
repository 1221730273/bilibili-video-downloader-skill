#!/usr/bin/env python3
"""
B站视频下载器 - 支持1080P高清下载
用法:
  python bilibili_downloader.py <BV号或视频URL> [--output-dir ./downloads] [--quality 80] [--cookie-file cookies.txt]

示例:
  python bilibili_downloader.py BV1QgG36EERX
  python bilibili_downloader.py "https://www.bilibili.com/video/BV1QgG36EERX" --output-dir ./videos
  python bilibili_downloader.py BV1QgG36EERX --cookie-file ~/.bili_cookies.txt --quality 80
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse

# 中文 Windows 控制台默认使用 GBK 编码，本脚本大量使用 emoji 输出状态，
# 在非交互/重定向场景下会抛 UnicodeEncodeError 直接中断。这里强制切换为 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", None) and _stream.encoding.lower().replace("-", "") != "utf8":
        _stream.reconfigure(encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    print("错误: 需要requests库，请运行 pip install requests")
    sys.exit(1)


# ============================================================
# 工具函数
# ============================================================

def extract_bvid(input_str):
    """从URL或纯文本中提取BV号"""
    # 匹配 BV + 10位字符（数字和字母）
    match = re.search(r'(BV[a-zA-Z0-9]{10})', input_str)
    if match:
        return match.group(1)
    return None


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|]', '', name).strip()


def load_cookies(cookie_file=None, cookie_string=None):
    """
    加载Cookie。优先级: cookie_string > cookie_file > 环境变量 BILI_COOKIE
    返回Cookie字典
    """
    cookies = {}
    
    raw_cookie = None
    
    if cookie_string:
        raw_cookie = cookie_string
    elif cookie_file and os.path.exists(cookie_file):
        with open(cookie_file, 'r', encoding='utf-8') as f:
            raw_cookie = f.read().strip()
    elif os.environ.get('BILI_COOKIE'):
        raw_cookie = os.environ['BILI_COOKIE']
    
    if not raw_cookie:
        return cookies
    
    # 解析Cookie字符串（支持 "key=value; key2=value2" 格式）
    for item in raw_cookie.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    
    return cookies


def check_ffmpeg():
    """检查ffmpeg是否可用"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ============================================================
# B站API客户端
# ============================================================

class BilibiliClient:
    """B站API客户端"""
    
    BASE_URL = "https://api.bilibili.com"
    
    # 清晰度代码映射
    QUALITY_MAP = {
        127: "8K",
        120: "4K",
        116: "1080P60",
        112: "1080P+",
        80: "1080P",
        64: "720P",
        32: "480P",
        16: "360P"
    }
    
    def __init__(self, cookies=None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bilibili.com"
        })
        self.cookies = cookies or {}
        # 设置cookie到session
        for key, value in self.cookies.items():
            self.session.cookies.set(key, value, domain=".bilibili.com")
    
    def _request(self, path, params=None, retry=3):
        """发送API请求，带重试"""
        url = f"{self.BASE_URL}{path}"
        
        for attempt in range(retry):
            try:
                resp = self.session.get(url, params=params, timeout=15)
                data = resp.json()
                
                code = data.get('code', -1)
                
                if code == 0:
                    return data['data']
                
                # 处理错误码
                if code == -412:
                    print(f"  [风控] 请求被拦截，等待5秒后重试 ({attempt+1}/{retry})...")
                    time.sleep(5)
                    continue
                elif code == -352:
                    print(f"  [安全] 请求被拦截，等待5秒后重试 ({attempt+1}/{retry})...")
                    time.sleep(5)
                    continue
                elif code == -101:
                    raise Exception("登录态已失效（-101）。请提供有效的SESSDATA等Cookie。")
                else:
                    raise Exception(f"API错误: code={code}, message={data.get('message', '未知错误')}")
                    
            except requests.exceptions.RequestException as e:
                if attempt < retry - 1:
                    print(f"  [网络错误] {e}，重试中 ({attempt+1}/{retry})...")
                    time.sleep(2)
                else:
                    raise Exception(f"网络请求失败: {e}")
        
        raise Exception("重试次数已用完，请求失败")
    
    def get_video_info(self, bvid):
        """
        获取视频基本信息
        返回: {title, cid, aid, duration, owner}
        """
        data = self._request("/x/web-interface/view", params={"bvid": bvid})
        
        return {
            "title": data["title"],
            "cid": data["cid"],
            "aid": data["aid"],
            "duration": data["duration"],
            "owner": data["owner"]["name"],
            "desc": data.get("desc", ""),
            "pages": data.get("pages", [])
        }
    
    def get_play_url(self, bvid, cid, quality=80):
        """
        获取播放地址，自动识别DASH格式（登录态）和durl格式（匿名）
        参数:
            quality: 清晰度代码 (80=1080P, 64=720P, 32=480P)
        返回: {mode, video_url, audio_url, durl_url, actual_quality, quality_name}
            mode="dash": 需要分别下载video和audio，再合并
            mode="durl": 直接下载一个MP4文件，无需合并
        """
        data = self._request("/x/player/playurl", params={
            "bvid": bvid,
            "cid": cid,
            "qn": quality,
            "fnval": 4048,
            "fourk": 1
        })
        
        actual_quality = data.get("quality", quality)
        quality_name = self.QUALITY_MAP.get(actual_quality, f"未知({actual_quality})")
        available_qualities = data.get("accept_quality", [])
        
        # 模式1：DASH格式（有Cookie时）
        dash = data.get("dash")
        if dash and dash.get("video"):
            # 选择视频流：优先指定清晰度的H.264编码
            video_stream = None
            
            for v in dash.get("video", []):
                if v["id"] == quality and v["codecs"].startswith("avc1"):
                    video_stream = v
                    break
            
            # 如果没找到指定清晰度，降级到720P
            if not video_stream:
                for v in dash.get("video", []):
                    if v["id"] == 64 and v["codecs"].startswith("avc1"):
                        video_stream = v
                        print(f"  [降级] 1080P不可用，已降至720P")
                        break
            
            # 再降级到480P
            if not video_stream:
                for v in dash.get("video", []):
                    if v["id"] == 32 and v["codecs"].startswith("avc1"):
                        video_stream = v
                        print(f"  [降级] 720P不可用，已降至480P")
                        break
            
            if not video_stream:
                video_stream = dash["video"][0]
            
            # 选择音频流：选码率最高的
            audio_streams = dash.get("audio", [])
            audio_stream = sorted(audio_streams, key=lambda x: x.get("bandwidth", 0), reverse=True)[0] if audio_streams else None
            
            return {
                "mode": "dash",
                "video_url": video_stream["baseUrl"],
                "video_backup": video_stream.get("backupUrl", [None])[0],
                "audio_url": audio_stream["baseUrl"] if audio_stream else None,
                "audio_backup": audio_stream.get("backupUrl", [None])[0] if audio_stream else None,
                "actual_quality": video_stream["id"],
                "quality_name": self.QUALITY_MAP.get(video_stream["id"], f"未知({video_stream['id']})"),
                "available_qualities": available_qualities
            }
        
        # 模式2：durl格式（匿名模式，直接MP4直链）
        durl = data.get("durl")
        if durl:
            return {
                "mode": "durl",
                "durl_url": durl[0]["url"],
                "durl_backup": durl[0].get("backup_url", [None])[0],
                "video_url": None,
                "audio_url": None,
                "actual_quality": actual_quality,
                "quality_name": quality_name,
                "available_qualities": available_qualities
            }
        
        raise Exception("未获取到播放流，可能是会员视频或格式不支持")


# ============================================================
# 下载与合并
# ============================================================

def download_stream(url, output_path, retries=3):
    """
    下载单个流文件（视频或音频）
    必须带Referer头，否则403
    """
    headers = {
        "Referer": "https://www.bilibili.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=headers, stream=True, timeout=300)
            resp.raise_for_status()
            
            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024*1024):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        pct = downloaded / total * 100
                        print(f"\r    进度: {pct:.1f}% ({downloaded/1024/1024:.1f}MB)", end="", flush=True)
            
            print()
            return True
            
        except Exception as e:
            print(f"\n    下载失败(尝试 {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(3)
    
    return False


def merge_av(video_path, audio_path, output_path):
    """
    用ffmpeg合并视频流和音频流为MP4
    使用 -c copy 不重新编码，秒完成
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c", "copy",
        "-movflags", "+faststart",
        output_path
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
    )
    
    if result.returncode != 0:
        # 如果copy失败，尝试重新编码
        print(f"    [信息] 直接拷贝失败，尝试重新编码...")
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
        
        if result.returncode != 0:
            raise Exception(f"ffmpeg合并失败: {result.stderr[-500:]}")
    
    return output_path


def verify_video(video_path):
    """验证视频文件完整性"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration,size:stream=width,height,codec_name",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30
        )
        return result.stdout.strip()
    except Exception:
        return None


# ============================================================
# 主流程
# ============================================================

def download_bilibili_video(url_or_bvid, output_dir="./downloads", quality=80,
                            cookies=None, keep_temp=False):
    """
    一键下载B站视频完整流程
    
    参数:
        url_or_bvid: 视频URL或BV号
        output_dir: 输出目录
        quality: 清晰度代码 (80=1080P)
        cookies: Cookie字典
        keep_temp: 是否保留临时m4s文件
    
    返回:
        成功返回输出文件路径，失败抛出异常
    """
    
    # 1. 提取BV号
    bvid = extract_bvid(url_or_bvid)
    if not bvid:
        raise Exception(f"无法从输入中提取BV号: {url_or_bvid}")
    print(f"📹 BV号: {bvid}")
    
    # 2. 检查ffmpeg
    if not check_ffmpeg():
        raise Exception("未找到ffmpeg。Windows: winget install Gyan.FFmpeg；Linux: apt install ffmpeg；macOS: brew install ffmpeg")
    
    # 3. 创建客户端
    client = BilibiliClient(cookies=cookies)
    
    # 4. 获取视频信息
    print("📋 获取视频信息...")
    info = client.get_video_info(bvid)
    print(f"   标题: {info['title']}")
    print(f"   UP主: {info['owner']}")
    print(f"   时长: {info['duration']//60}分{info['duration']%60}秒")
    
    # 5. 获取播放地址
    print(f"🔗 获取{client.QUALITY_MAP.get(quality, quality)}播放地址...")
    play = client.get_play_url(bvid, info['cid'], quality=quality)
    print(f"   实际清晰度: {play['quality_name']}")
    
    # 6. 准备输出路径
    os.makedirs(output_dir, exist_ok=True)
    safe_title = sanitize_filename(info['title'])
    output_path = os.path.join(output_dir, f"{safe_title}.mp4")
    
    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000000:
        print(f"⏭️  文件已存在，跳过: {output_path}")
        return output_path
    
    # 7. 根据播放模式下载
    video_tmp = os.path.join(tempfile.gettempdir(), f"{bvid}_video.m4s")
    audio_tmp = os.path.join(tempfile.gettempdir(), f"{bvid}_audio.m4s")
    
    if play["mode"] == "durl":
        # durl模式：直接下载完整MP4（匿名模式）
        print("⬇️  下载MP4文件（匿名模式，直接下载）...")
        if not download_stream(play['durl_url'], output_path):
            if play.get('durl_backup'):
                print("   主CDN失败，尝试备用CDN...")
                download_stream(play['durl_backup'], output_path)
    else:
        # dash模式：下载视频流+音频流，然后合并（登录态1080P）
        print("⬇️  下载视频流...")
        if not download_stream(play['video_url'], video_tmp):
            if play['video_backup']:
                print("   主CDN失败，尝试备用CDN...")
                download_stream(play['video_backup'], video_tmp)
        
        print("⬇️  下载音频流...")
        if not download_stream(play['audio_url'], audio_tmp):
            if play['audio_backup']:
                print("   主CDN失败，尝试备用CDN...")
                download_stream(play['audio_backup'], audio_tmp)
        
        print("🔄 合并音视频...")
        merge_av(video_tmp, audio_tmp, output_path)
        
        # 清理临时文件
        if not keep_temp:
            if os.path.exists(video_tmp):
                os.remove(video_tmp)
            if os.path.exists(audio_tmp):
                os.remove(audio_tmp)
    
    # 11. 验证
    file_size = os.path.getsize(output_path) / 1024 / 1024
    verify = verify_video(output_path)
    print(f"✅ 完成: {output_path}")
    print(f"   大小: {file_size:.1f}MB")
    if verify:
        print(f"   校验: {verify}")
    
    return output_path


def main():
    parser = argparse.ArgumentParser(description="B站视频下载器 - 支持1080P")
    parser.add_argument("url", help="视频URL或BV号")
    parser.add_argument("--output-dir", "-o", default="./downloads", help="输出目录 (默认: ./downloads)")
    parser.add_argument("--quality", "-q", type=int, default=80,
                        help="清晰度: 80=1080P, 64=720P, 32=480P (默认: 80)")
    parser.add_argument("--cookie-file", "-c", help="Cookie文件路径（含SESSDATA等）")
    parser.add_argument("--cookie", help="直接传入Cookie字符串")
    parser.add_argument("--keep-temp", action="store_true", help="保留临时m4s文件")
    
    args = parser.parse_args()
    
    # 加载cookie
    cookies = load_cookies(cookie_file=args.cookie_file, cookie_string=args.cookie)
    
    if not cookies:
        print("⚠️  未提供Cookie，将只能下载480P以下清晰度。")
        print("   如需1080P，请提供 --cookie-file 或 --cookie 参数")
        print("   Cookie获取方法: 浏览器登录B站后，F12 -> Application -> Cookies")
        print("   关键Cookie: SESSDATA, bili_jct, DedeUserID, DedeUserID__ckMd5")
        print()
    
    try:
        output = download_bilibili_video(
            args.url,
            output_dir=args.output_dir,
            quality=args.quality,
            cookies=cookies,
            keep_temp=args.keep_temp
        )
        print(f"\n🎉 下载成功: {output}")
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
