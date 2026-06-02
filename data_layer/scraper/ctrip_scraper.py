"""
携程旅游景点爬虫 (混合模式: Playwright + requests)
====================================================
策略:
  1. Playwright 加载列表页 → 获取 Cookie + 景点链接
  2. requests 复用 Cookie 爬取详情页 (快速、不反复启动浏览器)
  3. BeautifulSoup 解析HTML → 提取结构化数据
  4. 数据质量控制: 多选择器回退 + 正则补充

基于原有 scraper 重构，配置外部化，支持多页爬取。
"""

import json
import re
import time
from typing import List, Dict, Tuple, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from shared.config import ScraperConfig, RAW_DATA_DIR
from shared.logging_config import logger
from shared.exceptions import ScraperError, ScraperBlockedError
from data_layer.scraper.base_scraper import BaseScraper


# ============================================================
# 携程爬虫
# ============================================================

class CtripScraper(BaseScraper):
    """携程景点爬虫 - Playwright获取Cookie + requests爬详情"""

    def __init__(self, config: ScraperConfig = None):
        super().__init__(config)
        self._cookies: Optional[Dict] = None
        self._list_urls: List[str] = []

    # ============================================================
    # 列表页 (Playwright)
    # ============================================================

    def _playwright_get_cookies(self) -> Tuple[Dict, str]:
        """
        用Playwright加载列表首页获取Cookie。

        Returns:
            (cookies_dict, page_html)
        """
        logger.info("Playwright 加载列表页获取 Cookie...")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.config.PLAYWRIGHT_HEADLESS,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            context = browser.new_context(
                user_agent=self.random_ua(),
                viewport={'width': 1920, 'height': 1080},
                locale='zh-CN',
            )
            page = context.new_page()

            # 反检测脚本
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
                window.chrome = { runtime: {} };
            """)

            logger.info(f"  访问: {self.config.LIST_URL}")
            page.goto(self.config.LIST_URL, timeout=self.config.PLAYWRIGHT_TIMEOUT,
                       wait_until='domcontentloaded')
            time.sleep(self.config.PLAYWRIGHT_WAIT)

            html = page.content()
            logger.info(f"  页面加载完成: {len(html):,} 字节")

            # 获取Cookie
            pw_cookies = context.cookies()
            cookies_dict = {c['name']: c['value'] for c in pw_cookies}
            logger.info(f"  获取到 {len(cookies_dict)} 个Cookie")

            # 保存调试页面
            if len(html) < 1000:
                logger.error("  页面疑似被拦截，请稍后再试")
                browser.close()
                return {}, html

            browser.close()
            return cookies_dict, html

    def _parse_list_page(self, html: str) -> List[Dict]:
        """
        从列表页HTML中解析景点链接。

        Returns:
            [{'name': str, 'url': str}, ...]
        """
        soup = BeautifulSoup(html, 'html.parser')
        attractions = []
        seen_names = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # 匹配携程景点详情URL: /sight/{slug}/{poi_id}.html
            m = re.search(r'/sight/(?:shaoxing18|18)/(\d+)\.html', href)
            if not m:
                continue

            name = self.clean_text(a.get_text())
            if not name or len(name) < 2:
                continue
            # 跳过纯数字/符号文本
            if re.match(r'^[\d\s.,;:!?\-]+$', name):
                continue
            if name in seen_names:
                continue
            seen_names.add(name)

            # 标准化为完整HTTPS URL
            if href.startswith('//'):
                full_url = f"https:{href.split('?')[0]}"
            elif href.startswith('http'):
                full_url = href.split('?')[0]
            else:
                full_url = f"https://you.ctrip.com{href.split('?')[0]}"

            attractions.append({'name': name, 'url': full_url})

        logger.info(f"  从列表页解析到 {len(attractions)} 个景点链接")
        return attractions

    def fetch_list(self, page: int = 1) -> List[Dict]:
        """
        爬取单页列表。

        Args:
            page: 页码 (1-based)
        Returns:
            景点链接列表
        """
        if page == 1:
            # 首页用Playwright获取Cookie
            self._cookies, html = self._playwright_get_cookies()
            if len(html) < 1000:
                raise ScraperBlockedError("列表页被拦截，未获取到有效HTML")
            return self._parse_list_page(html)

        else:
            # 后续页用requests (复用Cookie)
            if not self._cookies:
                raise ScraperError("Cookie未初始化，请先调用page=1")

            url = self.config.LIST_URL_TEMPLATE.format(page=page)
            logger.info(f"  翻页: {url}")
            try:
                resp = self._request(url, cookies=self._cookies,
                                     referer=self.config.LIST_URL_TEMPLATE.format(page=page-1))
                return self._parse_list_page(resp.text)
            except ScraperError:
                logger.warning(f"  第{page}页加载失败，已到末页或Cookie过期")
                return []

    # ============================================================
    # 详情页 (requests + BeautifulSoup)
    # ============================================================

    def fetch_detail(self, url: str, name: str) -> Dict:
        """
        爬取单个景点详情页。

        Args:
            url: 详情页URL
            name: 景点名称 (备用)
        Returns:
            标准化的景点数据字典
        """
        result = self._empty_spot(name, url)

        try:
            resp = self._request(url, cookies=self._cookies, referer=self.config.LIST_URL)
        except ScraperError as e:
            logger.warning(f"  ⚠ {name}: 请求失败 - {e}")
            return result

        if len(resp.text) < 500:
            logger.warning(f"  ⚠ {name}: 响应内容过短 ({len(resp.text)}字节)")
            return result

        soup = BeautifulSoup(resp.text, 'html.parser')
        full_text = soup.get_text()

        # ---- 名称 ----
        result['name'] = self._extract_name(soup, name)

        # ---- 评分 ----
        result['rating'] = self._extract_rating(soup)

        # ---- 地址 ----
        result['address'] = self._extract_address(soup, full_text)

        # ---- 开放时间 ----
        result['open_time'] = self._extract_open_time(soup, full_text)

        # ---- 门票 ----
        result['ticket_price'] = self._extract_ticket(soup, full_text)

        # ---- 简介 ----
        result['summary'] = self._extract_summary(soup, full_text)

        # ---- 标签 ----
        result['tags'] = self._extract_tags(soup)

        # ---- 游玩时长 ----
        result['duration_raw'] = self._extract_duration(soup, full_text)

        # ---- 交通 ----
        result['transport_info'] = self._extract_transport(full_text)

        # ---- JSON-LD 结构化数据 ----
        self._extract_jsonld(soup, result)

        # ---- 评论数 ----
        result['review_count'] = self._extract_review_count(soup, full_text)

        return result

    def _empty_spot(self, name: str, url: str) -> Dict:
        """返回空的景点字典模板"""
        return {
            'name': name,
            'city': self.config.CITY_NAME,
            'address': '',
            'district': '',
            'open_time': '',
            'ticket_price': '',
            'duration_raw': '',
            'rating': 0,
            'review_count': 0,
            'tags': '',
            'category': '',
            'summary': '',
            'transport_info': '',
            'source_url': url,
            'source_platform': 'ctrip',
            'data_quality': 0,
            'popularity_score': 0,
        }

    # ---- 字段提取器 ----

    def _extract_name(self, soup: BeautifulSoup, fallback: str) -> str:
        """从title标签提取景点名称"""
        title_tag = soup.find('title')
        if title_tag:
            title_text = self.clean_text(title_tag.get_text())
            if '-' in title_text:
                parts = title_text.split('-')
                if parts[0] and len(parts[0]) >= 2:
                    return parts[0]
            elif title_text and len(title_text) < 30:
                return title_text
        return fallback

    def _extract_rating(self, soup: BeautifulSoup) -> float:
        """提取评分"""
        text = self.safe_find(soup, [
            '.gradeScore', '.commentScore', '.scoreText',
            '[class*="scoreNum"]', '.averageScore',
            'span[class*="grade"]', '.starNum',
        ])
        try:
            return float(text)
        except (ValueError, TypeError):
            return 0.0

    def _extract_address(self, soup: BeautifulSoup, full_text: str) -> str:
        """提取地址 (选择器 + 正则回退)"""
        addr = self.safe_find(soup, [
            '.address', '.scenicAddress', '.location',
            'span[class*="address"]', 'p[class*="addr"]',
        ])
        if addr:
            return addr

        # 正则回退
        for pat in [
            r'地址[：:]\s*(.{5,60}?)(?:[\n。]|$)',
            r'绍兴市.{2,30}(?:路|街|道|镇|村|号|区)',
        ]:
            m = re.search(pat, full_text)
            if m:
                return self.clean_text(m.group(0))
        return ''

    def _extract_open_time(self, soup: BeautifulSoup, full_text: str) -> str:
        """提取开放时间"""
        text = self.safe_find(soup, [
            '.openTime', '.businessHours', '.openingHours',
            'span[class*="openTime"]', 'div[class*="opening"]',
        ])
        if text:
            return text

        for pat in [
            r'(?:开放时间|营业时间)[：:]\s*(.{5,40}?)(?:[\n。]|$)',
            r'\d{2}:\d{2}\s*[-~至到]\s*\d{2}:\d{2}',
        ]:
            m = re.search(pat, full_text)
            if m:
                return self.clean_text(m.group(0))
        return ''

    def _extract_ticket(self, soup: BeautifulSoup, full_text: str) -> str:
        """提取门票价格"""
        text = self.safe_find(soup, [
            '.ticketPrice', '.priceText', '.scenicPrice',
            'span[class*="price"]', 'span[class*="ticket"]',
        ])
        if text:
            return text

        m = re.search(r'(?:门票|票价)[：:]\s*(.{3,30}?)(?:[\n。]|$)', full_text)
        if m:
            return self.clean_text(m.group(1))

        m = re.search(r'(免费|¥\s*\d+|￥\s*\d+|\d+\s*元起?)', full_text)
        if m:
            return m.group(1)
        return ''

    def _extract_summary(self, soup: BeautifulSoup, full_text: str) -> str:
        """提取简介"""
        text = self.safe_find(soup, [
            '.summary', '.scenicIntro', '.description',
            'div[class*="intro"]', 'div[class*="desc"]',
        ])
        if text:
            return text

        # meta description
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content'):
            content = self.clean_text(meta['content'])
            if len(content) > 10:
                return content

        # 取第一段长文本
        for p in soup.find_all('p'):
            text = self.clean_text(p.get_text())
            if 30 < len(text) < 500:
                return text
        return ''

    def _extract_tags(self, soup: BeautifulSoup) -> str:
        """提取标签"""
        tag_elems = soup.select('[class*="tag"], .label-item, .scenicTag, .themeTag')
        if tag_elems:
            tags = [self.clean_text(t.get_text()) for t in tag_elems[:8]
                    if self.clean_text(t.get_text())]
            return '|'.join(tags)
        return ''

    def _extract_duration(self, soup: BeautifulSoup, full_text: str) -> str:
        """提取建议游玩时长"""
        m = re.search(r'(?:建议|游玩|参考|游览)(?:时间|时长)[：:]\s*(.{3,20}?)(?:[\n。]|$)', full_text)
        if m:
            return self.clean_text(m.group(1))

        m = re.search(r'(\d+[-~]\d+\s*(?:小时|天|分钟))', full_text)
        if m:
            return m.group(1)

        m = re.search(r'([\d.]+\s*(?:小时|天|分钟))', full_text)
        if m:
            return m.group(1)
        return ''

    def _extract_transport(self, full_text: str) -> str:
        """提取交通信息"""
        for pat in [
            r'(?:交通|公交)[：:]\s*(.{8,80}?)(?:[\n。]|$)',
            r'(?:乘坐|搭乘|可乘).{3,40}?(?:公交|地铁|巴士|路|线)',
        ]:
            m = re.search(pat, full_text)
            if m:
                return self.clean_text(m.group(0))
        return ''

    def _extract_review_count(self, soup: BeautifulSoup, full_text: str) -> int:
        """提取评论数"""
        text = self.safe_find(soup, ['.commentCount', '[class*="reviewCount"]', '.reviewNum'])
        if text:
            nums = re.findall(r'\d+', text)
            if nums:
                return int(nums[0])
        return 0

    def _extract_jsonld(self, soup: BeautifulSoup, result: Dict):
        """从JSON-LD结构化数据中补充信息"""
        for script in soup.find_all('script', type='application/ld+json'):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # 地址
                    if not result['address']:
                        addr = data.get('address', {})
                        if isinstance(addr, dict):
                            result['address'] = addr.get('streetAddress', '')
                        elif isinstance(addr, str):
                            result['address'] = addr
                    # 评分
                    if not result['rating']:
                        agg = data.get('aggregateRating', {})
                        if isinstance(agg, dict):
                            try:
                                result['rating'] = float(agg.get('ratingValue', 0))
                            except (ValueError, TypeError):
                                pass
                    # 评论数
                    if not result['review_count']:
                        agg = data.get('aggregateRating', {})
                        if isinstance(agg, dict):
                            try:
                                result['review_count'] = int(agg.get('reviewCount', 0))
                            except (ValueError, TypeError):
                                pass
            except json.JSONDecodeError:
                pass

    # ============================================================
    # 爬取流程
    # ============================================================

    def run(self, max_items: int = None) -> List[Dict]:
        """
        执行完整爬取流程: 列表页 → 详情页。

        Args:
            max_items: 最大爬取数量 (默认使用config)
        Returns:
            景点数据字典列表
        """
        max_items = max_items or self.config.MAX_SPOTS
        all_links = []
        all_spots = []

        # Step 1: 收集列表页链接
        logger.info(f"=== Phase 1: 列表页采集 ({self.config.CITY_NAME}, 最多{max_items}个) ===")

        for page in range(1, self.config.MAX_PAGES + 1):
            if max_items and len(all_links) >= max_items:
                break

            try:
                links = self.fetch_list(page)
                if not links:
                    logger.info(f"第{page}页无更多景点，停止翻页")
                    break
                all_links.extend(links)
                logger.info(f"  已累计 {len(all_links)} 个链接")

                if page < self.config.MAX_PAGES:
                    self.random_delay()
            except ScraperBlockedError as e:
                logger.error(f"列表页被拦截: {e}")
                break

        # 截断
        all_links = all_links[:max_items] if max_items else all_links
        logger.info(f"共收集到 {len(all_links)} 个景点链接")

        # Step 2: 爬取详情页
        logger.info(f"=== Phase 2: 详情页采集 ===")

        for i, link in enumerate(all_links):
            logger.info(f"  [{i+1}/{len(all_links)}] {link['name']}")

            if i > 0:
                self.random_delay()

            detail = self.fetch_detail(link['url'], link['name'])
            all_spots.append(detail)

            # 简要输出
            fields = {k: str(v)[:50] for k, v in detail.items() if v}
            logger.debug(f"    提取字段: {list(fields.keys())}")

        logger.info(f"详情采集完成: {len(all_spots)} 个景点")
        return all_spots


# ============================================================
# 便捷函数
# ============================================================

def run_ctrip_scraper(max_items: int = None, headless: bool = False) -> List[Dict]:
    """
    运行携程爬虫的便捷入口。

    Args:
        max_items: 最大景点数
        headless: 是否无头模式
    Returns:
        景点数据列表
    """
    config = ScraperConfig()
    config.PLAYWRIGHT_HEADLESS = headless
    if max_items:
        config.MAX_SPOTS = max_items

    scraper = CtripScraper(config)
    return scraper.run()
