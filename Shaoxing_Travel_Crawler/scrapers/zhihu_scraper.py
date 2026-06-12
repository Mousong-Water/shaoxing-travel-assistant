"""
知乎搜索采集 (真实requests + 静态回退)
======================================
策略: 访问知乎搜索页HTML (无需登录可浏览标题和摘要)
URL: https://www.zhihu.com/search?type=content&q=绍兴旅游

合规: 仅访问搜索页公开内容, 不登录、不爬全文
"""

import logging
from typing import List, Dict
from urllib.parse import quote

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "绍兴旅游攻略", "绍兴有什么好玩的地方", "绍兴美食推荐",
    "绍兴周边游", "绍兴古镇推荐", "绍兴三日游", "绍兴亲子游",
]

# 静态回退 (知乎高赞回答摘要, 真实爬取失败时使用)
ZHIHU_FALLBACK = [
    {"标题":"绍兴有哪些值得去的景点？","摘要":"鲁迅故里(必去)、沈园(陆游唐婉)、东湖(乌篷船)、兰亭(书法圣地)、柯岩鉴湖鲁镇。如果时间充裕可加安昌古镇和新昌大佛寺。","赞同":"1200","标签":"景点推荐"},
    {"标题":"绍兴2-3天自由行怎么安排？","摘要":"D1:鲁迅故里+沈园+书圣故里+仓桥直街。D2:柯岩鉴湖鲁镇。D3:东湖+兰亭。住宿越城区200-400元。","赞同":"890","标签":"行程规划"},
    {"标题":"绍兴有什么必吃的美食？","摘要":"梅干菜扣肉、清汤越鸡、绍兴三臭、茴香豆配黄酒。老字号:咸亨酒店、同心楼、荣禄春。","赞同":"2300","标签":"美食推荐"},
    {"标题":"绍兴哪些景点是免费的？","摘要":"鲁迅故里(身份证领票)、书圣故里、仓桥直街、八字桥、安昌古镇(大门票)、府山公园免费。","赞同":"1500","标签":"实用信息"},
    {"标题":"绍兴旅游避坑指南","摘要":"兰亭离市区远预留半天。东湖乌篷船85元略贵但值得。安昌古镇周末人超多。柯岩穿运动鞋。夏天做好防晒。","赞同":"3200","标签":"避雷指南"},
]


class ZhihuScraper:
    """知乎搜索采集 (真实HTTP + 静态回退)"""

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=2.0, delay_max=4.0, max_retries=2)
        self.max_items = max_items or 80
        self._platform = "zhihu"

    def run(self) -> List[Dict]:
        results = []

        # 1. 真实搜索
        live_results = self._scrape_live()
        results.extend(live_results)
        logger.info(f"知乎实时: {len(live_results)} 条")

        # 2. 回退
        if len(results) < 5:
            for post in ZHIHU_FALLBACK:
                results.append({
                    "标题": post["标题"],
                    "摘要": post["摘要"],
                    "赞同": post["赞同"],
                    "标签": post["标签"],
                    "来源平台": "zhihu_fallback",
                    "来源URL": f"zhihu_static:{post['标题'][:20]}",
                    "_data_category": "attraction_review",
                    "_trust_level": 1,
                })
            logger.info(f"知乎回退: {len(ZHIHU_FALLBACK)} 条")

        return results[:self.max_items]

    def _scrape_live(self) -> List[Dict]:
        """真实抓取知乎搜索页"""
        results = []
        seen = set()

        for query in SEARCH_QUERIES:
            if len(results) >= 30:
                break
            try:
                url = f"https://www.zhihu.com/search?type=content&q={quote(query)}"
                resp, tag = self.rm.get(url)

                if tag != 'ok':
                    logger.debug(f"知乎搜索[{query}]: {tag}")
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                for item in soup.select('.List-item, .SearchResultCard, [class*="SearchResult"]')[:5]:
                    title_el = item.select_one('[class*="title"], h2 a, .ContentItem-title a')
                    snippet_el = item.select_one('[class*="excerpt"], [class*="content"], .RichText')
                    vote_el = item.select_one('[class*="vote"], [class*="like"]')

                    if title_el:
                        title = clean_text(title_el.get_text())
                        snippet = clean_text(snippet_el.get_text()) if snippet_el else ""
                        href = title_el.get('href', '')
                        if 'question' in href or 'answer' in href:
                            if 'zhihu.com' not in href:
                                href = 'https://www.zhihu.com' + href

                        if title and len(title) > 3 and title not in seen:
                            seen.add(title)
                            results.append({
                                "标题": title[:80],
                                "摘要": snippet[:200] if snippet else "",
                                "赞同": clean_text(vote_el.get_text()) if vote_el else "",
                                "搜索词": query,
                                "来源平台": "zhihu",
                                "来源URL": href if href.startswith('http') else url,
                                "_data_category": "attraction_review",
                                "_trust_level": 2,
                            })
            except Exception as e:
                logger.debug(f"知乎搜索异常 [{query}]: {e}")
                continue

        return results
