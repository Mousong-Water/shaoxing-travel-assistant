"""
马蜂窝攻略采集 (继承ScraperMixin)
==================================
URL去重 + 可配置阈值 + 字段统一

合规: 仅访问公开搜索页、不登录、合理频率
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
    "绍兴旅游攻略", "绍兴景点", "绍兴美食", "绍兴古镇",
    "绍兴三日游", "绍兴亲子", "绍兴周边",
]

FALLBACK = [
    {"景点":"鲁迅故里","建议":"建议上午9点前到达避开人流","路线":"鲁迅祖居→三味书屋→百草园→鲁迅纪念馆","耗时":"2-3小时","url":"https://www.mafengwo.cn/search/s.php?q=鲁迅故里"},
    {"景点":"沈园","建议":"下午3点后入园，白天赏园+傍晚看演出","路线":"断云石→孤鹤轩→钗头凤碑→葫芦池","耗时":"1.5-2小时","url":"https://www.mafengwo.cn/search/s.php?q=沈园"},
    {"景点":"东湖","建议":"乘乌篷船进、步行出","路线":"码头→陶公洞→仙桃洞→听湫亭","耗时":"2-3小时","url":"https://www.mafengwo.cn/search/s.php?q=东湖"},
    {"景点":"兰亭景区","建议":"春天最佳竹林新绿曲水流觞","路线":"鹅池碑→流觞亭→御碑亭→王右军祠","耗时":"2-3小时","url":"https://www.mafengwo.cn/search/s.php?q=兰亭"},
    {"景点":"柯岩风景区","建议":"安排半天柯岩看石鉴湖坐船鲁镇看演出","路线":"入口→大佛→云骨→鉴湖→鲁镇","耗时":"3-4小时","url":"https://www.mafengwo.cn/search/s.php?q=柯岩"},
    {"景点":"安昌古镇","建议":"腊月最佳年味最浓","路线":"入口→仁昌酱园→老街→师爷馆","耗时":"2-3小时","url":"https://www.mafengwo.cn/search/s.php?q=安昌古镇"},
]


class MafengwoScraper(ScraperMixin):
    """马蜂窝攻略采集"""

    def __init__(self, max_items: int = 30, **kwargs):
        super().__init__(
            max_items=max_items,
            max_per_query=kwargs.pop('max_per_query', 5),
            min_live_threshold=kwargs.pop('min_live_threshold', 5),
            max_live_total=kwargs.pop('max_live_total', 25),
            query_list=kwargs.pop('query_list', DEFAULT_QUERIES),
        )
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)

    def _platform_name(self) -> str:
        return "mafengwo"

    def _scrape_live(self) -> List[Dict]:
        """真实抓取马蜂窝搜索页"""
        results = []

        for query in self.query_list:
            if len(results) >= self.max_live_total:
                break
            try:
                url = f"https://www.mafengwo.cn/search/s.php?q={quote(query)}"
                resp, tag = self.rm.get(url)
                if tag != 'ok':
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.select('.search-list .item, [class*="search-item"], .list-item'):
                    if len(results) >= self.max_live_total:
                        break
                    a_tag = item.select_one('h3 a, [class*="title"] a, a[href*="/poi/"]')
                    desc_el = item.select_one('[class*="desc"], .summary, p')

                    if a_tag:
                        href = a_tag.get('href', '')
                        if href and not href.startswith('http'):
                            href = 'https://www.mafengwo.cn' + href
                        if self.is_duplicate(href):
                            continue

                        results.append(self.make_item({
                            "标题": clean_text(a_tag.get_text())[:50],
                            "摘要": clean_text(desc_el.get_text())[:200] if desc_el else "",
                            "链接": href,
                            "搜索词": query,
                            "来源URL": href,
                        }))
            except Exception as e:
                logger.debug(f"马蜂窝[{query}]: {e}")
                continue

        return results

    def _fallback_data(self) -> List[Dict]:
        """静态回退"""
        return [
            self.make_item({
                "标题": f"{fb['景点']}攻略",
                "摘要": f"建议:{fb['建议']} | 路线:{fb['路线']} | 耗时:{fb['耗时']}",
                "链接": fb["url"],
                "来源URL": fb["url"],
                "来源平台": "mafengwo_fallback",
                "_trust_level": 1,
            })
            for fb in FALLBACK
        ]
