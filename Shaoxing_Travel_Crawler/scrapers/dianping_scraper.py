"""
大众点评搜索采集 (真实requests + 静态回退)
==========================================
策略: 访问大众点评搜索页 (无需登录可浏览搜索结果摘要)
URL: https://www.dianping.com/search/keyword/7/0_{关键词}

合规: 仅访问搜索列表页、不登录、合理频率(3-5s)
"""

import logging
import re
from typing import List, Dict
from urllib.parse import quote

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

SEARCH_KEYWORDS = [
    "绍兴老字号", "绍兴本帮菜", "绍兴小吃", "绍兴面馆",
    "绍兴黄酒", "绍兴特产", "绍兴早餐",
]

# 静态回退 (18家绍兴知名店铺)
SHAOXING_SHOPS_FALLBACK = [
    {"店名":"咸亨酒店","类型":"绍兴菜·老字号","地址":"越城区鲁迅中路179号","人均":"80-120元","推荐":"茴香豆、绍兴黄酒、梅干菜扣肉","简介":"清光绪二十年(1894年)创建，因鲁迅小说《孔乙己》闻名"},
    {"店名":"寻宝记绍兴菜","类型":"绍兴菜·网红","地址":"越城区仓桥直街114号","人均":"70-100元","推荐":"醉蟹、梅干菜扣肉、宋嫂鱼羹","简介":"仓桥直街核心位置，常年排队"},
    {"店名":"同心楼","类型":"小吃面点·百年老店","地址":"越城区解放北路430号","人均":"15-30元","推荐":"生煎包、片儿川","简介":"百年老店，生煎包底脆肉鲜汁多"},
    {"店名":"状元楼","类型":"绍兴菜·老牌","地址":"越城区胜利西路","人均":"60-90元","推荐":"清汤越鸡、干菜焖肉","简介":"绍兴老牌酒楼"},
    {"店名":"孔乙己酒家","类型":"绍兴菜·主题","地址":"越城区鲁迅中路273号","人均":"70-100元","推荐":"茴香豆、花雕鸡","简介":"鲁迅主题绍兴菜馆"},
    {"店名":"高老太奶油小攀","类型":"甜品·老字号","地址":"越城区新建南路","人均":"8-15元","推荐":"奶油小攀","简介":"绍兴独有传统甜品，开了三十多年"},
    {"店名":"绘璟轩·黄酒奶茶","type":"饮品·网红","地址":"越城区仓桥直街","人均":"20-35元","推荐":"黄酒奶茶、黄酒拿铁","简介":"绍兴黄酒新喝法代表"},
    {"店名":"仓桥阿丘面馆","type":"面馆","地址":"越城区仓桥直街","人均":"15-25元","推荐":"次坞打面、片儿川","简介":"仓桥直街地道面馆"},
]


class DianpingScraper:
    """大众点评搜索采集 (真实HTTP + 静态回退)"""

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)
        self.max_items = max_items

    def run(self) -> List[Dict]:
        results = []

        # 1. 真实搜索
        live_results = self._scrape_live()
        results.extend(live_results)
        logger.info(f"点评实时: {len(live_results)} 条")

        # 2. 回退
        if len(results) < 8:
            for shop in SHAOXING_SHOPS_FALLBACK:
                results.append({
                    "店名": shop["店名"], "类型": shop["类型"],
                    "地址": shop["地址"], "人均": shop.get("人均", ""),
                    "推荐": shop["推荐"], "简介": shop["简介"],
                    "来源平台": "dianping_fallback",
                    "来源URL": f"dianping_static:{shop['店名']}",
                    "_data_category": "food_shop",
                    "_trust_level": 1,
                })
            logger.info(f"点评回退: {len(SHAOXING_SHOPS_FALLBACK)} 条")

        return results[:self.max_items] if self.max_items else results

    def _scrape_live(self) -> List[Dict]:
        """真实抓取大众点评搜索页"""
        results = []
        seen = set()

        for kw in SEARCH_KEYWORDS:
            if len(results) >= 20:
                break
            try:
                url = f"https://www.dianping.com/search/keyword/7/0_{quote(kw)}"
                resp, tag = self.rm.get(url)

                if tag == 'blocked':
                    logger.debug(f"点评被拦截 [{kw}]")
                    break
                if tag != 'ok':
                    continue

                soup = BeautifulSoup(resp.text, 'html.parser')

                for card in soup.select('.shop-list li, .shop-item, [class*="shop"]')[:5]:
                    name_el = card.select_one('h4, [class*="title"] a, a[href*="/shop/"]')
                    addr_el = card.select_one('[class*="addr"], .address, .tag-addr')
                    price_el = card.select_one('[class*="price"], .avg-price')

                    if name_el:
                        name = clean_text(name_el.get_text())
                        if name and len(name) > 1 and name not in seen:
                            seen.add(name)
                            results.append({
                                "店名": name[:30],
                                "地址": clean_text(addr_el.get_text()) if addr_el else "",
                                "人均": clean_text(price_el.get_text()) if price_el else "",
                                "搜索词": kw,
                                "来源平台": "dianping",
                                "来源URL": url,
                                "_data_category": "food_shop",
                                "_trust_level": 2,
                            })
            except Exception as e:
                logger.debug(f"点评搜索异常 [{kw}]: {e}")
                continue

        return results
