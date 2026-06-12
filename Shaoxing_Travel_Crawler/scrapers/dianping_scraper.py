"""
大众点评搜索采集 (继承ScraperMixin)
====================================
URL去重 + 可配置阈值 + 字段统一

合规: 仅访问搜索列表页、不登录、合理频率
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
    "绍兴老字号", "绍兴本帮菜", "绍兴小吃", "绍兴面馆",
    "绍兴黄酒", "绍兴特产", "绍兴早餐",
]

FALLBACK = [
    {"店名":"咸亨酒店","类型":"绍兴菜·老字号","地址":"越城区鲁迅中路179号","人均":"80-120元","推荐":"茴香豆、绍兴黄酒、梅干菜扣肉","url":"https://www.dianping.com/search/keyword/7/0_咸亨酒店"},
    {"店名":"寻宝记绍兴菜","类型":"绍兴菜·网红","地址":"越城区仓桥直街114号","人均":"70-100元","推荐":"醉蟹、梅干菜扣肉","url":"https://www.dianping.com/search/keyword/7/0_寻宝记"},
    {"店名":"同心楼","类型":"小吃面点","地址":"越城区解放北路430号","人均":"15-30元","推荐":"生煎包、片儿川","url":"https://www.dianping.com/search/keyword/7/0_同心楼"},
    {"店名":"状元楼","类型":"绍兴菜·老牌","地址":"越城区胜利西路","人均":"60-90元","推荐":"清汤越鸡、干菜焖肉","url":"https://www.dianping.com/search/keyword/7/0_状元楼"},
    {"店名":"孔乙己酒家","类型":"绍兴菜·主题","地址":"越城区鲁迅中路273号","人均":"70-100元","推荐":"茴香豆、花雕鸡","url":"https://www.dianping.com/search/keyword/7/0_孔乙己酒家"},
    {"店名":"高老太奶油小攀","类型":"甜品·老字号","地址":"越城区新建南路","人均":"8-15元","推荐":"奶油小攀","url":"https://www.dianping.com/search/keyword/7/0_奶油小攀"},
    {"店名":"绘璟轩·黄酒奶茶","类型":"饮品·网红","地址":"越城区仓桥直街","人均":"20-35元","推荐":"黄酒奶茶、黄酒拿铁","url":"https://www.dianping.com/search/keyword/7/0_黄酒奶茶"},
    {"店名":"仓桥阿丘面馆","类型":"面馆","地址":"越城区仓桥直街","人均":"15-25元","推荐":"次坞打面、片儿川","url":"https://www.dianping.com/search/keyword/7/0_阿丘面馆"},
]


class DianpingScraper(ScraperMixin):
    """大众点评搜索采集"""

    def __init__(self, max_items: int = 30, **kwargs):
        super().__init__(
            max_items=max_items,
            max_per_query=kwargs.pop('max_per_query', 5),
            min_live_threshold=kwargs.pop('min_live_threshold', 8),
            max_live_total=kwargs.pop('max_live_total', 25),
            query_list=kwargs.pop('query_list', DEFAULT_QUERIES),
        )
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)

    def _platform_name(self) -> str:
        return "dianping"

    def _scrape_live(self) -> List[Dict]:
        """真实抓取大众点评搜索页"""
        results = []

        for kw in self.query_list:
            if len(results) >= self.max_live_total:
                break
            try:
                url = f"https://www.dianping.com/search/keyword/7/0_{quote(kw)}"
                resp, tag = self.rm.get(url)
                if tag == 'blocked':
                    logger.debug(f"点评被拦截，停止实时采集")
                    break
                if tag != 'ok':
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')
                for card in soup.select('.shop-list li, .shop-item, [class*="shop"]'):
                    if len(results) >= self.max_live_total:
                        break
                    name_el = card.select_one('h4 a, [class*="title"] a, a[href*="/shop/"]')
                    addr_el = card.select_one('[class*="addr"], .address')
                    price_el = card.select_one('[class*="price"], .avg-price')

                    if name_el:
                        href = name_el.get('href', '')
                        if self.is_duplicate(href):
                            continue

                        results.append(self.make_item({
                            "标题": clean_text(name_el.get_text())[:30],
                            "摘要": f"地址:{clean_text(addr_el.get_text()) if addr_el else ''} 人均:{clean_text(price_el.get_text()) if price_el else ''}",
                            "链接": href,
                            "搜索词": kw,
                            "来源URL": url,
                            "_data_category": "food_shop",
                        }))
            except Exception as e:
                logger.debug(f"点评[{kw}]: {e}")
                continue

        return results

    def _fallback_data(self) -> List[Dict]:
        """静态回退"""
        return [
            self.make_item({
                "标题": fb["店名"],
                "摘要": f"{fb['类型']} | {fb['地址']} | 人均{fb['人均']} | 推荐:{fb['推荐']}",
                "链接": fb["url"],
                "来源URL": fb["url"],
                "来源平台": "dianping_fallback",
                "_data_category": "food_shop",
                "_trust_level": 1,
            })
            for fb in FALLBACK
        ]
