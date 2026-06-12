"""
知乎搜索采集 (继承ScraperMixin)
================================
URL去重 + 可配置阈值 + 字段统一 + 点赞数字化

合规: 仅访问搜索页公开内容, 不登录、不爬全文
"""

import logging
from typing import List, Dict
from urllib.parse import quote

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text
from crawler_utils.scraper_mixin import ScraperMixin

logger = logging.getLogger(__name__)

DEFAULT_QUERIES = [
    "绍兴旅游攻略", "绍兴有什么好玩的地方", "绍兴美食推荐",
    "绍兴周边游", "绍兴古镇推荐", "绍兴三日游", "绍兴亲子游",
]

# 静态回退
FALLBACK = [
    {"标题":"绍兴有哪些值得去的景点？","摘要":"鲁迅故里(必去)、沈园(陆游唐婉)、东湖(乌篷船)、兰亭(书法圣地)、柯岩鉴湖鲁镇。","点赞":1200,"url":"https://www.zhihu.com/search?q=绍兴景点"},
    {"标题":"绍兴2-3天自由行怎么安排？","摘要":"D1:鲁迅故里+沈园+书圣故里+仓桥直街。D2:柯岩鉴湖鲁镇。D3:东湖+兰亭。","点赞":890,"url":"https://www.zhihu.com/search?q=绍兴攻略"},
    {"标题":"绍兴有什么必吃的美食？","摘要":"梅干菜扣肉、清汤越鸡、绍兴三臭、茴香豆配黄酒。","点赞":2300,"url":"https://www.zhihu.com/search?q=绍兴美食"},
    {"标题":"绍兴哪些景点是免费的？","摘要":"鲁迅故里、书圣故里、仓桥直街、八字桥、安昌古镇大门票免费。","点赞":1500,"url":"https://www.zhihu.com/search?q=绍兴免费"},
    {"标题":"绍兴旅游避坑指南","摘要":"兰亭离市区远预留半天。东湖乌篷船85元略贵但值得。安昌古镇周末人超多。","点赞":3200,"url":"https://www.zhihu.com/search?q=绍兴避坑"},
]


class ZhihuScraper(ScraperMixin):
    """知乎搜索采集"""

    def __init__(self, max_items: int = 80, **kwargs):
        super().__init__(
            max_items=max_items,
            max_per_query=kwargs.pop('max_per_query', 8),
            min_live_threshold=kwargs.pop('min_live_threshold', 5),
            max_live_total=kwargs.pop('max_live_total', 40),
            query_list=kwargs.pop('query_list', DEFAULT_QUERIES),
        )
        self.rm = RequestManager(delay_min=2.0, delay_max=4.0, max_retries=2)

    def _platform_name(self) -> str:
        return "zhihu"

    def _scrape_live(self) -> List[Dict]:
        """真实抓取知乎搜索页"""
        results = []

        for query in self.query_list:
            if len(results) >= self.max_live_total:
                break
            try:
                url = f"https://www.zhihu.com/search?type=content&q={quote(query)}"
                resp, tag = self.rm.get(url)
                if tag != 'ok':
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.select('.List-item, .SearchResultCard, [class*="SearchResult"]'):
                    if len(results) >= self.max_live_total:
                        break

                    a_tag = item.select_one('a[href*="question"], a[href*="answer"]')
                    snippet_el = item.select_one('[class*="excerpt"], [class*="content"], .RichText')
                    vote_el = item.select_one('[class*="vote"], [class*="like"]')

                    if a_tag:
                        href = a_tag.get('href', '')
                        if href and not href.startswith('http'):
                            href = 'https://www.zhihu.com' + href

                        # URL去重
                        if self.is_duplicate(href):
                            continue

                        entry = self.make_item({
                            "标题": clean_text(a_tag.get_text())[:80],
                            "摘要": clean_text(snippet_el.get_text())[:200] if snippet_el else "",
                            "链接": href,
                            "搜索词": query,
                            "点赞": self.parse_likes(clean_text(vote_el.get_text()) if vote_el else ""),
                            "来源URL": href,
                        })
                        results.append(entry)
            except Exception as e:
                logger.debug(f"知乎[{query}]: {e}")
                continue

        return results

    def _fallback_data(self) -> List[Dict]:
        """静态回退"""
        return [
            self.make_item({
                "标题": fb["标题"],
                "摘要": fb["摘要"],
                "链接": fb["url"],
                "点赞": fb["点赞"],
                "来源URL": fb["url"],
                "来源平台": "zhihu_fallback",
                "_trust_level": 1,
            })
            for fb in FALLBACK
        ]
