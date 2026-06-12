"""
马蜂窝攻略采集 (真实requests + 静态回退)
========================================
策略: 访问马蜂窝搜索页 + 景点攻略页
URL: https://www.mafengwo.cn/search/s.php?q=绍兴

合规: 仅访问公开页面、不登录、合理频率(3-5s)
"""

import logging
from typing import List, Dict
from urllib.parse import quote

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

SEARCH_QUERIES = [
    "绍兴旅游攻略", "绍兴景点", "绍兴美食", "绍兴古镇",
    "绍兴三日游", "绍兴亲子", "绍兴周边",
]

# 静态回退 (12条攻略)
GUIDES_FALLBACK = [
    {"景点":"鲁迅故里","游玩建议":"建议上午9点前到达避开人流高峰","推荐游览顺序":"鲁迅祖居→三味书屋→百草园→鲁迅纪念馆","耗时":"2-3小时","贴士":"免费不免票需凭身份证领票"},
    {"景点":"沈园","游玩建议":"下午3点后入园，白天赏园+傍晚看演出","推荐游览顺序":"断云石→孤鹤轩→钗头凤碑→葫芦池","耗时":"1.5-2小时","贴士":"夜游演出需另购票"},
    {"景点":"东湖","游玩建议":"乘乌篷船进、步行出","推荐游览顺序":"码头→陶公洞→仙桃洞→听湫亭","耗时":"2-3小时","贴士":"乌篷船85元另购；节假日排队"},
    {"景点":"兰亭景区","游玩建议":"春天最佳竹林新绿曲水流觞","推荐游览顺序":"鹅池碑→流觞亭→御碑亭→王右军祠","耗时":"2-3小时","贴士":"三月初三书法节最热闹"},
    {"景点":"柯岩风景区","游玩建议":"安排半天柯岩看石鉴湖坐船鲁镇看演出","推荐游览顺序":"入口→大佛→云骨→鉴湖→葫芦醉岛→鲁镇","耗时":"3-4小时","贴士":"联票115元含三景区"},
    {"景点":"安昌古镇","游玩建议":"腊月最佳年味最浓","推荐游览顺序":"入口→仁昌酱园→老街→师爷馆","耗时":"2-3小时","贴士":"扯白糖现场制作可观看"},
]


class MafengwoScraper:
    """马蜂窝攻略采集 (真实HTTP + 静态回退)"""

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)
        self.max_items = max_items

    def run(self) -> List[Dict]:
        results = []

        # 1. 真实抓取
        live_results = self._scrape_live()
        results.extend(live_results)
        logger.info(f"马蜂窝实时: {len(live_results)} 条")

        # 2. 回退
        if len(results) < 5:
            for guide in GUIDES_FALLBACK:
                results.append({
                    "景点": guide["景点"],
                    "游玩建议": guide["游玩建议"],
                    "推荐游览顺序": guide["推荐游览顺序"],
                    "耗时": guide["耗时"],
                    "贴士": guide["贴士"],
                    "来源平台": "mafengwo_fallback",
                    "来源URL": f"mafengwo_static:{guide['景点']}",
                    "_data_category": "attraction_review",
                    "_trust_level": 1,
                })
            logger.info(f"马蜂窝回退: {len(GUIDES_FALLBACK)} 条")

        return results[:self.max_items] if self.max_items else results

    def _scrape_live(self) -> List[Dict]:
        """真实抓取马蜂窝搜索页"""
        results = []
        seen = set()

        for query in SEARCH_QUERIES:
            if len(results) >= 20:
                break
            try:
                url = f"https://www.mafengwo.cn/search/s.php?q={quote(query)}"
                resp, tag = self.rm.get(url)

                if tag != 'ok':
                    logger.debug(f"马蜂窝搜索[{query}]: {tag}")
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                for item in soup.select('.search-list .item, [class*="search-item"], .list-item')[:5]:
                    title_el = item.select_one('h3 a, [class*="title"] a, a[href*="/poi/"]')
                    desc_el = item.select_one('[class*="desc"], .summary, p')

                    if title_el:
                        title = clean_text(title_el.get_text())
                        href = title_el.get('href', '')
                        if title and len(title) > 2 and title not in seen:
                            seen.add(title)
                            results.append({
                                "景点": title[:50],
                                "游玩建议": clean_text(desc_el.get_text())[:200] if desc_el else "",
                                "搜索词": query,
                                "来源平台": "mafengwo",
                                "来源URL": href if href.startswith('http') else f"https://www.mafengwo.cn{href}" if href else url,
                                "_data_category": "attraction_review",
                                "_trust_level": 2,
                            })
            except Exception as e:
                logger.debug(f"马蜂窝搜索异常 [{query}]: {e}")
                continue

        return results
