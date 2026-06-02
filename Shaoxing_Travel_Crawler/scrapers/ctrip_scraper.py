"""
携程景点爬虫
================================
继承 BaseScraper，使用 RequestManager + parser_utils 提取器。
解决短板: #1 #2 #3 #5 #6 #7 #8 #16 #17 #18

渲染模式 (解决短板 #16 #17):
  requests   - 纯requests (最快，但可能被拦截)
  playwright - 纯Playwright (最稳，但慢)
  auto       - requests优先，4xx时自动降级Playwright (推荐)

使用示例:
    scraper = CtripScraper(render_mode='auto', max_spots=30)
    spots = scraper.run()
"""

import logging
import random
import re
import time
from typing import List, Dict, Tuple, Optional

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, make_empty_spot
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import (
    clean_text, safe_find,
    AddressExtractor, OpenTimeExtractor, TicketExtractor,
    RatingExtractor, SummaryExtractor, DurationExtractor,
    TransportExtractor, TagsExtractor,
    parse_attraction_links, fill_from_jsonld,
)

logger = logging.getLogger(__name__)


class CtripScraper(BaseScraper):
    """
    携程旅游景点爬虫。

    流程:
      1. Playwright 获取Cookie (解决WAF)
      2. 列表页: Playwright (首页) / requests (翻页)
      3. 详情页: requests (auto模式) / Playwright (回退)
      4. 提取器: parser_utils.FieldExtractor 子类
    """

    def __init__(
        self,
        city_slug: str = 'shaoxing18',
        city_name: str = '绍兴',
        max_spots: int = 50,
        max_pages: int = 3,
        render_mode: str = 'auto',       # 'requests' | 'playwright' | 'auto'
        playwright_headless: bool = False,
        **kwargs,
    ):
        """
        Args:
            city_slug: 携程URL城市标识 (如 shaoxing18, hangzhou14)
            city_name: 中文城市名
            max_spots: 最多爬取数量
            max_pages: 最多翻页数
            render_mode: 详情页渲染模式
            playwright_headless: Playwright是否无头模式
        """
        list_url = f"https://you.ctrip.com/sight/{city_slug}/s0-p1.html"
        super().__init__(
            city_name=city_name,
            list_url=list_url,
            max_spots=max_spots,
            max_pages=max_pages,
            platform_name='ctrip',
            **kwargs,
        )

        self.city_slug = city_slug
        self.render_mode = render_mode
        self.playwright_headless = playwright_headless

        # 请求管理器 (解决短板 #5 #7 #8)
        self.rm = RequestManager(
            delay_min=self.delay_min,
            delay_max=self.delay_max,
            max_retries=3,
        )

        # Cookie存储
        self._cookies: Dict[str, str] = {}

        # Playwright实例 (懒加载, 解决短板 #18: 不复用浏览器)
        self._playwright = None
        self._browser = None
        self._page = None

    # ---- Playwright管理 (解决短板 #18) ----

    def _init_playwright(self):
        """懒初始化 Playwright (仅首次使用时启动)"""
        if self._browser is not None:
            return  # 已初始化，复用

        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.playwright_headless,
            args=['--disable-blink-features=AutomationControlled', '--no-sandbox'],
        )
        context = self._browser.new_context(
            user_agent=self.rm._build_headers().get('User-Agent', ''),
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        self._page = context.new_page()

        # 反检测脚本
        self._page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
            window.chrome = { runtime: {} };
        """)

        logger.info("Playwright浏览器已启动 (复用模式)")

    def _close_playwright(self):
        """关闭Playwright"""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        self._page = None
        logger.info("Playwright浏览器已关闭")

    # ---- Cookie获取 (解决短板 #9: Cookie过期检测) ----

    def _before_run(self):
        """运行前: 用Playwright获取Cookie"""
        self._init_playwright()
        self._cookies = self._acquire_cookies()
        # 将Cookie同步到RequestManager的session
        for name, value in self._cookies.items():
            self.rm.session.cookies.set(name, value, domain='you.ctrip.com')

    def _acquire_cookies(self) -> Dict[str, str]:
        """Playwright加载列表首页获取Cookie"""
        logger.info("Playwright获取Cookie...")
        self._page.goto(self.list_url, timeout=60000, wait_until='domcontentloaded')
        time.sleep(5)

        pw_cookies = self._page.context.cookies()
        cookies_dict = {c['name']: c['value'] for c in pw_cookies}
        logger.info(f"获取到 {len(cookies_dict)} 个Cookie: {list(cookies_dict.keys())[:6]}")
        return cookies_dict

    # ---- 列表页 ----

    def fetch_list(self, page: int = 1) -> List[Dict]:
        """
        爬取列表页。

        首页: Playwright (绕过WAF)
        翻页: requests (复用Cookie, 更快)
        """
        if page == 1:
            return self._fetch_list_playwright()
        else:
            return self._fetch_list_requests(page)

    def _fetch_list_playwright(self) -> List[Dict]:
        """Playwright加载首页并解析链接"""
        html = self._page.content()
        logger.info(f"首页内容: {len(html):,}字节")

        if len(html) < 1000:
            logger.error("首页疑似被拦截")

        # 保存调试HTML
        debug_path = self.output_dir / "debug_ctrip_list.html"
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(html)

        soup = BeautifulSoup(html, 'html.parser')
        return parse_attraction_links(soup)

    def _fetch_list_requests(self, page: int) -> List[Dict]:
        """requests翻页"""
        url = f"https://you.ctrip.com/sight/{self.city_slug}/s0-p{page}.html"
        logger.info(f"翻页: {url}")

        resp, tag = self.rm.get(url, cookies=self._cookies, referer=self.list_url)

        if tag != 'ok':
            logger.warning(f"第{page}页请求失败: {tag}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_attraction_links(soup)

    # ---- 详情页 (解决短板 #16 #17: 渲染模式配置 + 自动降级) ----

    def fetch_detail(self, url: str, name: str) -> Dict:
        """
        爬取详情页，根据 render_mode 选择策略:

        auto模式流程:
          1. requests尝试 → 成功返回
          2. 被拦截 → Playwright回退
        """
        if self.render_mode == 'playwright':
            return self._fetch_detail_playwright(url, name)
        elif self.render_mode == 'requests':
            return self._fetch_detail_requests(url, name)
        else:  # auto
            result = self._fetch_detail_requests(url, name)
            # 判断是否需要回退: 所有关键字段都为空时回退
            filled = sum(1 for k in ['地址', '开放时间', '评分', '简介']
                         if result.get(k))
            if filled < 2 and self._cookies:
                logger.info(f"  requests提取字段不足({filled}/4)，回退Playwright")
                return self._fetch_detail_playwright(url, name)
            return result

    def _fetch_detail_requests(self, url: str, name: str) -> Dict:
        """requests爬详情 (快速模式)"""
        result = make_empty_spot(
            name=name, city=self.city_name, url=url, platform='ctrip',
        )

        resp, tag = self.rm.get(url, cookies=self._cookies, referer=self.list_url)

        if tag != 'ok':
            if tag == 'blocked':
                logger.warning(f"  requests被拦截 [{name}]")
                result['_blocked'] = True  # 标记供auto模式判断
            return result

        soup = BeautifulSoup(resp.text, 'html.parser')
        full_text = soup.get_text()

        # 使用提取器 (解决短板 #2 #3: 选择器统一管理)
        result['名称'] = self._extract_name(soup, name)
        result['地址'] = AddressExtractor.extract(soup, full_text)
        result['开放时间'] = OpenTimeExtractor.extract(soup, full_text)
        result['门票价格'] = TicketExtractor.extract(soup, full_text)
        result['评分'] = RatingExtractor.extract(soup, full_text)
        result['简介'] = SummaryExtractor.extract(soup, full_text)
        result['游玩时长'] = DurationExtractor.extract(soup, full_text)
        result['交通'] = TransportExtractor.extract(soup, full_text)
        result['标签'] = TagsExtractor.extract(soup)

        # JSON-LD补充
        fill_from_jsonld(soup, result)

        # 评论数
        review_text = safe_find(soup, ['.commentCount', '[class*="reviewCount"]'])
        if review_text:
            nums = re.findall(r'\d+', review_text)
            if nums:
                result['评论数'] = int(nums[0])

        # 清理空值 (解决短板 #14)
        for k, v in result.items():
            if v is None:
                result[k] = '' if k != '评论数' else 0

        return result

    def _fetch_detail_playwright(self, url: str, name: str) -> Dict:
        """Playwright爬详情 (回退模式)"""
        result = make_empty_spot(
            name=name, city=self.city_name, url=url, platform='ctrip',
        )

        try:
            self._page.goto(url, timeout=30000, wait_until='domcontentloaded')
            time.sleep(2)
        except Exception as e:
            logger.error(f"  Playwright加载失败 [{name}]: {e}")
            return result

        html = self._page.content()
        if len(html) < 500:
            return result

        soup = BeautifulSoup(html, 'html.parser')
        full_text = soup.get_text()

        # 使用同样的提取器
        result['名称'] = self._extract_name(soup, name)
        result['评分'] = RatingExtractor.extract(soup, full_text)
        result['地址'] = AddressExtractor.extract(soup, full_text)
        result['开放时间'] = OpenTimeExtractor.extract(soup, full_text)
        result['门票价格'] = TicketExtractor.extract(soup, full_text)
        result['简介'] = SummaryExtractor.extract(soup, full_text)
        result['标签'] = TagsExtractor.extract(soup)

        return result

    # ---- 辅助方法 ----

    def _extract_name(self, soup: BeautifulSoup, fallback: str) -> str:
        """从title标签提取景点名称 (原 L235-243)"""
        title_tag = soup.find('title')
        if title_tag:
            title_text = clean_text(title_tag.get_text())
            if '-' in title_text:
                parts = title_text.split('-')
                if parts[0] and len(parts[0]) >= 2:
                    return parts[0]
            elif title_text and len(title_text) < 30:
                return title_text
        return fallback

    def _after_run(self, results: List[Dict]):
        """运行后: 关闭Playwright"""
        self._close_playwright()

    def run(self, max_items: int = None) -> List[Dict]:
        """执行爬取 (含异常保护)"""
        try:
            return super().run(max_items)
        except Exception as e:
            logger.error(f"爬取异常: {e}", exc_info=True)
            raise
        finally:
            self._close_playwright()
