"""
携程绍兴旅游景点爬虫 (混合模式: Playwright + requests)
============================================================
策略：
  1. Playwright 启动浏览器加载列表页 → 获取 Cookie + 景点链接列表
  2. requests 复用 Playwright 的 Cookie 爬取详情页 → 速度快，无需反复启动浏览器
  3. BeautifulSoup 解析 HTML → 提取结构化数据
  4. 保存为 CSV (utf-8-sig 编码)

目标: 携程绍兴景点 (you.ctrip.com/sight/shaoxing18/)
提取: 名称、城市、地址、开放时间、门票价格、游玩时长、评分、标签、简介、交通
"""

import csv
import json
import os
import random
import re
import time
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ============================================================
# 配置区
# ============================================================

# 工作目录
WORK_DIR = Path(r"D:\Shaoxing_Travel\Shaoxing_Travel_Crawler")
WORK_DIR.mkdir(parents=True, exist_ok=True)

# 目标URL
LIST_URL = "https://you.ctrip.com/sight/shaoxing18/s0-p1.html"
CITY_NAME = "绍兴"

# 最大爬取数量（测试用3个）
MAX_SPOTS = 3

# 请求间隔（秒）
DELAY = 2

# 输出文件
OUTPUT_CSV = WORK_DIR / f"shaoxing_attractions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


# ============================================================
# 工具函数
# ============================================================

def random_ua() -> str:
    return random.choice(USER_AGENTS)


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def safe_find(soup, selectors: list, default: str = "") -> str:
    """安全提取文本，按优先级尝试多个CSS选择器"""
    for sel in selectors:
        elem = soup.select_one(sel)
        if elem:
            text = clean_text(elem.get_text())
            if text:
                return text
    return default


# ============================================================
# Phase 1: Playwright 获取Cookie和景点链接
# ============================================================

def get_cookies_and_links() -> tuple:
    """
    用Playwright加载列表页，返回 (cookies_dict, attraction_links_list, page_html)
    - cookies_dict: 可传给 requests 的 cookie 字典
    - attraction_links_list: [{'name': str, 'url': str}, ...]
    - page_html: 列表页HTML，供分析用
    """
    print("[Phase 1] Playwright 加载列表页...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
        )
        context = browser.new_context(
            user_agent=random_ua(),
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        page = context.new_page()

        # 注入反检测脚本
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            window.chrome = { runtime: {} };
        """)

        print(f"  访问: {LIST_URL}")
        page.goto(LIST_URL, timeout=60000, wait_until='domcontentloaded')
        time.sleep(5)  # 等待JS渲染

        html = page.content()
        print(f"  页面加载完成: {len(html):,} 字节")

        if len(html) < 1000:
            print("  ✗ 页面被拦截，请稍后再试")
            browser.close()
            return {}, [], ""

        # --- 获取Cookie（转为requests可用的dict） ---
        pw_cookies = context.cookies()
        cookies_dict = {c['name']: c['value'] for c in pw_cookies}
        print(f"  获取到 {len(cookies_dict)} 个Cookie: {list(cookies_dict.keys())[:6]}")

        # --- 解析景点链接 ---
        soup = BeautifulSoup(html, 'html.parser')
        attractions = []
        seen_names = set()

        # 匹配携程景点详情页URL（两种格式）:
        #   格式1: https://you.ctrip.com/sight/shaoxing18/{id}.html?poiType=3&scene=online
        #   格式2: http://you.ctrip.com/sight/18/{id}.html
        for a in soup.find_all('a', href=True):
            href = a['href']
            # 匹配 sight/城市名+数字/{poi_id}.html 格式
            m = re.search(r'/sight/(?:shaoxing18|18)/(\d+)\.html', href)
            if not m:
                continue

            # 提取景点名称（a标签文本）
            name = clean_text(a.get_text())
            if not name or len(name) < 2:
                continue
            # 跳过纯数字、纯英文、非景点文本
            if re.match(r'^[\d\s\.\,\;\:\!\?\-]+$', name):
                continue

            # 去重（按名称）
            if name in seen_names:
                continue
            seen_names.add(name)

            # 标准化为完整HTTPS URL（去掉查询参数）
            if href.startswith('//'):
                full_url = f"https:{href.split('?')[0]}"
            elif href.startswith('http'):
                full_url = href.split('?')[0]
            else:
                full_url = f"https://you.ctrip.com{href.split('?')[0]}"

            attractions.append({'name': name, 'url': full_url})

        print(f"  找到 {len(attractions)} 个景点链接")

        # 保存列表页HTML供调试
        debug_html = WORK_DIR / "debug_list_page.html"
        with open(debug_html, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"  调试: 列表页HTML已保存到 {debug_html}")

        browser.close()
        return cookies_dict, attractions, html


# ============================================================
# Phase 2: requests 爬取详情页
# ============================================================

def scrape_detail_with_requests(url: str, cookies: dict, name: str) -> dict:
    """
    使用 requests + BeautifulSoup 爬取单个景点详情页。
    复用 Playwright 获取的 Cookie。
    """
    result = {
        '名称': name,
        '城市': CITY_NAME,
        '地址': '',
        '开放时间': '',
        '门票价格': '',
        '游玩时长': '',
        '评分': '',
        '标签': '',
        '简介': '',
        '交通': '',
    }

    headers = {
        'User-Agent': random_ua(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': LIST_URL,
        'Connection': 'keep-alive',
    }

    try:
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
        resp.encoding = 'utf-8'
    except requests.RequestException as e:
        print(f"    ⚠ 请求失败: {e}")
        return result

    if resp.status_code != 200:
        print(f"    ⚠ HTTP {resp.status_code}, 可能被拦截")
        return result

    if len(resp.text) < 500:
        print(f"    ⚠ 响应内容过短 ({len(resp.text)}字节), 可能被拦截")
        return result

    soup = BeautifulSoup(resp.text, 'html.parser')
    full_text = soup.get_text()

    # --- 景点名称（title标签）---
    title_tag = soup.find('title')
    if title_tag:
        title_text = clean_text(title_tag.get_text())
        # 携程标题格式: "景点名-门票-地址-开放时间-携程攻略"
        if '-' in title_text:
            parts = title_text.split('-')
            if parts[0] and len(parts[0]) >= 2:
                result['名称'] = parts[0]
        elif title_text and len(title_text) < 30:
            result['名称'] = title_text

    # --- 评分 ---
    result['评分'] = safe_find(soup, [
        '.gradeScore', '.commentScore', '.scoreText',
        '[class*="scoreNum"]', '.averageScore',
        'span[class*="grade"]', '.starNum',
    ])

    # --- 地址 ---
    result['地址'] = safe_find(soup, [
        '.address', '.scenicAddress', '.location',
        'span[class*="address"]', 'p[class*="addr"]',
    ])

    # --- 开放时间 ---
    result['开放时间'] = safe_find(soup, [
        '.openTime', '.businessHours', '.openingHours',
        'span[class*="openTime"]', 'div[class*="opening"]',
    ])

    # --- 门票 ---
    result['门票价格'] = safe_find(soup, [
        '.ticketPrice', '.priceText', '.scenicPrice',
        'span[class*="price"]', 'span[class*="ticket"]',
    ])

    # --- 简介 ---
    result['简介'] = safe_find(soup, [
        '.summary', '.scenicIntro', '.description',
        'div[class*="intro"]', 'div[class*="desc"]',
        'meta[name="description"]',
    ])
    if not result['简介']:
        # 尝试取第一段较长的文本作为简介
        for p in soup.find_all('p'):
            text = clean_text(p.get_text())
            if len(text) > 30 and len(text) < 500:
                result['简介'] = text
                break

    # --- 标签 ---
    tag_elems = soup.select('[class*="tag"], .label-item, .scenicTag, .themeTag')
    if tag_elems:
        result['标签'] = '|'.join(
            clean_text(t.get_text()) for t in tag_elems[:8] if clean_text(t.get_text())
        )

    # --- 结构化数据 (JSON-LD) ---
    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if not result['地址']:
                        addr = data.get('address', {})
                        result['地址'] = addr.get('streetAddress', '') if isinstance(addr, dict) else str(addr)
                    if not result['评分']:
                        agg = data.get('aggregateRating', {})
                        result['评分'] = str(agg.get('ratingValue', '')) if isinstance(agg, dict) else ''
            except json.JSONDecodeError:
                pass

    # --- 正则补充提取 ---
    # 地址
    if not result['地址']:
        for pat in [
            r'地址[：:]\s*(.{5,60}?)(?:[\n。]|$)',
            r'绍兴市.{2,30}(?:路|街|道|镇|村|号|区)',
        ]:
            m = re.search(pat, full_text)
            if m:
                result['地址'] = clean_text(m.group(0))
                break

    # 开放时间
    if not result['开放时间']:
        for pat in [
            r'(?:开放时间|营业时间)[：:]\s*(.{5,40}?)(?:[\n。]|$)',
            r'\d{2}:\d{2}\s*[-~至到]\s*\d{2}:\d{2}',
        ]:
            m = re.search(pat, full_text)
            if m:
                result['开放时间'] = clean_text(m.group(0))
                break

    # 门票
    if not result['门票价格']:
        m = re.search(r'(?:门票|票价)[：:]\s*(.{3,30}?)(?:[\n。]|$)', full_text)
        if m:
            result['门票价格'] = clean_text(m.group(1))
        else:
            m = re.search(r'(免费|¥\s*\d+|￥\s*\d+|\d+\s*元起?)', full_text)
            if m:
                result['门票价格'] = m.group(1)

    # 游玩时长
    m = re.search(r'(?:建议|游玩|参考|游览)(?:时间|时长)[：:]\s*(.{3,20}?)(?:[\n。]|$)', full_text)
    if m:
        result['游玩时长'] = clean_text(m.group(1))
    if not result['游玩时长']:
        m = re.search(r'(\d+[-~]\d+\s*(?:小时|天|分钟))', full_text)
        if m:
            result['游玩时长'] = m.group(1)

    # 交通
    for pat in [
        r'(?:交通|公交)[：:]\s*(.{8,80}?)(?:[\n。]|$)',
        r'(?:乘坐|搭乘|可乘).{3,40}?(?:公交|地铁|巴士|路|线)',
    ]:
        m = re.search(pat, full_text)
        if m:
            result['交通'] = clean_text(m.group(0))
            break

    return result


# ============================================================
# Phase 3: 回退方案（requests失败时用Playwright）
# ============================================================

def scrape_detail_with_playwright(page, url: str, name: str) -> dict:
    """当requests被拦截时，用Playwright作为回退"""
    result = {
        '名称': name, '城市': CITY_NAME,
        '地址': '', '开放时间': '', '门票价格': '',
        '游玩时长': '', '评分': '', '标签': '', '简介': '', '交通': '',
    }

    try:
        page.goto(url, timeout=30000, wait_until='domcontentloaded')
        time.sleep(2)
    except Exception as e:
        print(f"    ⚠ Playwright加载失败: {e}")
        return result

    html = page.content()
    if len(html) < 500:
        return result

    soup = BeautifulSoup(html, 'html.parser')
    full_text = soup.get_text()

    # 复用同样的提取逻辑
    result['评分'] = safe_find(soup, ['.gradeScore', '.commentScore', '[class*="score"]'])
    result['地址'] = safe_find(soup, ['.address', '[class*="address"]', '.location'])
    result['开放时间'] = safe_find(soup, ['.openTime', '[class*="openTime"]'])
    result['门票价格'] = safe_find(soup, ['.ticketPrice', '[class*="ticket"]'])
    result['简介'] = safe_find(soup, ['.summary', '[class*="intro"]', 'meta[name="description"]'])

    tag_elems = soup.select('[class*="tag"], .label-item')
    if tag_elems:
        result['标签'] = '|'.join(clean_text(t.get_text()) for t in tag_elems[:8] if clean_text(t.get_text()))

    # 正则补充
    if not result['地址']:
        m = re.search(r'地址[：:]\s*(.{5,60}?)(?:[\n。]|$)', full_text)
        if m: result['地址'] = clean_text(m.group(0))
    if not result['开放时间']:
        m = re.search(r'\d{2}:\d{2}\s*[-~至到]\s*\d{2}:\d{2}', full_text)
        if m: result['开放时间'] = m.group(0)
    if not result['门票价格']:
        m = re.search(r'(免费|¥\s*\d+|￥\s*\d+)', full_text)
        if m: result['门票价格'] = m.group(1)

    return result


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("  绍兴旅游景点爬虫 (混合模式)")
    print(f"  目标: {LIST_URL}")
    print(f"  限制: {MAX_SPOTS} 个景点")
    print(f"  输出: {OUTPUT_CSV}")
    print("=" * 60)

    # --- Step 1: Playwright获取Cookie和链接 ---
    cookies, attractions, list_html = get_cookies_and_links()

    if not attractions:
        print("\n✗ 未能提取到景点链接，请检查目标页面结构是否变化")
        print("  提示: 查看 debug_list_page.html 分析页面结构")
        return

    # 限制数量
    attractions = attractions[:MAX_SPOTS]

    # --- Step 2: 测试requests是否可用 ---
    print(f"\n[Phase 2] 测试 requests 可行性...")
    use_requests = False
    if cookies:
        test_url = attractions[0]['url']
        try:
            test_resp = requests.get(
                test_url,
                headers={'User-Agent': random_ua(), 'Referer': LIST_URL},
                cookies=cookies,
                timeout=15
            )
            if test_resp.status_code == 200 and len(test_resp.text) > 1000:
                print(f"  ✓ requests 可用! 状态码: 200, 内容: {len(test_resp.text):,} 字节")
                use_requests = True
            else:
                print(f"  ✗ requests 被拦截 (状态:{test_resp.status_code}, 长度:{len(test_resp.text)})")
        except Exception as e:
            print(f"  ✗ requests 测试失败: {e}")
    else:
        print("  ✗ 无可用Cookie")

    # --- Step 3: 爬取详情页 ---
    print(f"\n[Phase 3] 爬取景点详情 ({'requests' if use_requests else 'Playwright'} 模式)...")

    results = []

    if use_requests:
        # 纯requests模式（更快）
        for i, attr in enumerate(attractions):
            print(f"\n  [{i+1}/{len(attractions)}] {attr['name']}")
            print(f"      URL: {attr['url']}")

            if i > 0:
                delay = DELAY + random.uniform(0, 1)
                time.sleep(delay)

            detail = scrape_detail_with_requests(attr['url'], cookies, attr['name'])
            results.append(detail)

            for k, v in detail.items():
                if v:
                    print(f"      {k}: {v[:60]}")
    else:
        # Playwright回退模式
        print("  requests不可用，使用Playwright回退模式...")
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = browser.new_context(
                user_agent=random_ua(),
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )
            page = context.new_page()
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = { runtime: {} };
            """)

            for i, attr in enumerate(attractions):
                print(f"\n  [{i+1}/{len(attractions)}] {attr['name']}")
                print(f"      URL: {attr['url']}")

                if i > 0:
                    delay = DELAY + random.uniform(0, 1)
                    time.sleep(delay)

                detail = scrape_detail_with_playwright(page, attr['url'], attr['name'])
                results.append(detail)

                for k, v in detail.items():
                    if v:
                        print(f"      {k}: {v[:60]}")

            browser.close()

    # --- Step 4: 保存CSV ---
    print(f"\n{'='*60}")
    print(f"  保存结果...")

    if results:
        fieldnames = ['名称', '城市', '地址', '开放时间', '门票价格', '游玩时长', '评分', '标签', '简介', '交通']
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in results:
                writer.writerow(row)

        print(f"\n  ✓ 已保存 {len(results)} 个景点到:")
        print(f"    {OUTPUT_CSV}")

        # 预览
        print(f"\n  {'='*40}")
        print(f"  CSV 内容预览")
        print(f"  {'='*40}")
        for row in results:
            for k, v in row.items():
                if v:
                    print(f"    {k}: {v}")
            print(f"    {'-'*30}")
    else:
        print("  ✗ 无数据可保存")

    print(f"\n完成!")
    return results


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n运行异常: {e}")
        import traceback
        traceback.print_exc()
