#!/usr/bin/env python3
"""
B站Cookie自动获取工具
自动打开浏览器，用户扫码/账号登录后，自动保存Cookie到文件。
无需手动打开DevTools复制。

用法:
  python get_cookies.py                          # 默认保存到 bilibili_cookies.txt
  python get_cookies.py --output my_cookies.txt  # 指定保存路径
  python get_cookies.py --browser chrome          # 使用Chrome（默认chromium）

Windows 首次使用需安装:
  pip install playwright
  playwright install chromium
"""

import argparse
import json
import os
import sys
import time

# 中文 Windows 控制台默认使用 GBK 编码，本脚本使用 emoji 输出状态，
# 在非交互/重定向场景下会抛 UnicodeEncodeError 直接中断。这里强制切换为 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", None) and _stream.encoding.lower().replace("-", "") != "utf8":
        _stream.reconfigure(encoding="utf-8", errors="replace")


def get_bilibili_cookies(output_path="bilibili_cookies.txt", browser_type="chromium", timeout=300):
    """
    自动打开B站登录页，等待用户登录后保存Cookie。
    
    流程:
    1. 打开浏览器到B站登录页
    2. 用户扫码或输入账号密码登录
    3. 自动检测登录成功（检测到SESSDATA）
    4. 保存所有Cookie到文件
    
    Args:
        output_path: Cookie保存路径
        browser_type: 浏览器类型 (chromium/chrome/msedge/firefox)
        timeout: 最大等待秒数（默认5分钟）
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("=" * 60)
        print("错误: 未安装playwright")
        print("请先运行以下命令安装:")
        print("  pip install playwright")
        print("  playwright install chromium")
        print("=" * 60)
        sys.exit(1)

    print("=" * 60)
    print("  B站Cookie自动获取工具")
    print("=" * 60)
    print()
    print("即将打开浏览器，请在浏览器中登录B站账号。")
    print("支持扫码登录或账号密码登录。")
    print("登录成功后会自动检测并保存Cookie，无需手动操作。")
    print()

    with sync_playwright() as p:
        # 启动浏览器
        if browser_type == "chrome":
            browser = p.chromium.launch(headless=False, channel="chrome")
        elif browser_type == "msedge":
            browser = p.chromium.launch(headless=False, channel="msedge")
        elif browser_type == "firefox":
            browser = p.firefox.launch(headless=False)
        else:
            browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 打开B站登录页
        page.goto("https://passport.bilibili.com/login", wait_until="domcontentloaded")
        print("浏览器已打开B站登录页。")
        print(f"等待登录中...（最长等待{timeout//60}分钟）")
        print()

        # 轮询检测登录状态
        start_time = time.time()
        logged_in = False
        cookies = []

        while time.time() - start_time < timeout:
            # 检查是否有SESSDATA（登录成功的标志）
            cookies = context.cookies("https://www.bilibili.com")
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            
            if "SESSDATA" in cookie_dict and cookie_dict["SESSDATA"]:
                logged_in = True
                elapsed = int(time.time() - start_time)
                print(f"✅ 检测到登录成功！（用时{elapsed}秒）")
                break
            
            # 每10秒提示一次
            elapsed = int(time.time() - start_time)
            if elapsed % 10 == 0 and elapsed > 0:
                print(f"  仍在等待登录...（已等待{elapsed}秒）")
            
            time.sleep(2)

        if not logged_in:
            print(f"\n⏰ 等待超时（{timeout}秒），未检测到登录。")
            browser.close()
            sys.exit(1)

        # 稍等一下确保Cookie完整写入
        time.sleep(1)
        cookies = context.cookies("https://www.bilibili.com")
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        # 检查关键Cookie
        required = ["SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5"]
        missing = [k for k in required if k not in cookie_dict]
        if missing:
            print(f"⚠️  警告: 缺少关键Cookie: {', '.join(missing)}")
            print("   下载1080P可能需要这些Cookie。")
        
        # 保存为Netscape cookie格式和key=value格式两种
        # 格式1: 一行式 key=value; key2=value2（供下载脚本用 --cookie 读取）
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookie_dict.items())
        
        # 格式2: JSON格式（备份）
        # 原实现用 output_path.replace(".txt", ".json")：当路径不含 .txt 时
        # （如 --output cookies/bilibili），两个路径会指向同一文件，txt 被 JSON 覆盖。
        json_path = (output_path[:-4] + ".json") if output_path.endswith(".txt") else (output_path + ".json")

        # 保存（先建目录，否则 SKILL.md 推荐的 cookies/bilibili.txt 会因目录不存在而失败）
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cookie_str)
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print()
        print(f"✅ Cookie已保存到:")
        print(f"   {os.path.abspath(output_path)}")
        print(f"   {os.path.abspath(json_path)} (JSON备份)")
        print()
        print(f"获取到的Cookie列表:")
        for name in ["SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", 
                      "buvid3", "buvid4", "buvid_fp"]:
            if name in cookie_dict:
                val = cookie_dict[name]
                print(f"   ✓ {name} = {val[:30]}...")
        
        # 显示用户名
        try:
            page.goto("https://api.bilibili.com/x/web-interface/nav", wait_until="domcontentloaded")
            # 这里原本有一句局部 `import json`，会把 json 变成整个函数的局部名，
            # 导致前面保存 JSON 备份时的 json.dump 抛 UnboundLocalError 而中断。
            resp = page.evaluate("() => document.body.innerText")
            nav_data = json.loads(resp)
            if nav_data.get("data", {}).get("isLogin"):
                uname = nav_data["data"].get("uname", "未知")
                print(f"\n登录用户: {uname}")
        except Exception:
            pass

        browser.close()
        print()
        print("现在可以用下载脚本了:")
        print(f'  python bilibili_downloader.py "<BV号>" --cookie-file "{os.path.abspath(output_path)}"')


def main():
    parser = argparse.ArgumentParser(description="B站Cookie自动获取工具")
    parser.add_argument("--output", "-o", default="bilibili_cookies.txt", 
                        help="Cookie保存路径（默认: bilibili_cookies.txt）")
    parser.add_argument("--browser", "-b", default="chromium",
                        choices=["chromium", "chrome", "msedge", "firefox"],
                        help="使用的浏览器（默认: chromium）")
    parser.add_argument("--timeout", "-t", type=int, default=300,
                        help="最大等待登录秒数（默认: 300秒=5分钟）")
    
    args = parser.parse_args()
    get_bilibili_cookies(args.output, args.browser, args.timeout)


if __name__ == "__main__":
    main()
