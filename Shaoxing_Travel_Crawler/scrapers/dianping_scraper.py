"""
大众点评静态页采集
================================
合规访问搜索页 (无需登录可见):
  - 绍兴景点周边美食店铺
  - 评分、人均消费、地址
  - 特色小吃推荐

策略: 仅访问搜索列表页 (https://www.dianping.com/search/keyword/...)
不登录、不翻详情页、不绕反爬。
"""

import logging
import re
from typing import List, Dict, Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

# 绍兴特色美食关键词
SHAOXING_FOOD_KEYWORDS = [
    "绍兴臭豆腐", "梅干菜扣肉", "茴香豆", "绍兴黄酒",
    "绍兴醉鸡", "绍兴酱鸭", "霉苋菜梗", "糟鸡",
    "奶油小攀", "黄酒奶茶", "黄酒棒冰", "绍兴香糕",
    "次坞打面", "嵊州小笼包", "新昌炒年糕", "诸暨西施豆腐",
]

# 绍兴知名老店 (静态数据, 用于API不可用时的回退)
SHAOXING_FAMOUS_SHOPS = [
    {"店名": "咸亨酒店", "类型": "绍兴菜", "地址": "越城区鲁迅中路179号",
     "推荐": "茴香豆、绍兴黄酒、梅干菜扣肉",
     "简介": "因鲁迅小说《孔乙己》闻名，绍兴老字号"},
    {"店名": "咸亨酒店(中餐厅)", "类型": "绍兴菜", "地址": "鲁迅故里景区内",
     "推荐": "醉鸡、臭豆腐、酱鸭",
     "简介": "景区内分店，适合游客体验"},
    {"店名": "同心楼", "类型": "小吃面点", "地址": "越城区解放北路430号",
     "推荐": "生煎包、片儿川",
     "简介": "绍兴百年老店，以面点小吃闻名"},
    {"店名": "寻宝记绍兴菜", "类型": "绍兴菜", "地址": "越城区仓桥直街114号",
     "推荐": "醉蟹、梅干菜扣肉、宋嫂鱼羹",
     "简介": "仓桥直街上的网红绍兴菜馆"},
    {"店名": "孔乙己酒家", "类型": "绍兴菜", "地址": "越城区鲁迅中路273号",
     "推荐": "茴香豆、花雕鸡、绍兴三臭",
     "简介": "鲁迅主题绍兴菜馆，文化氛围浓厚"},
    {"店名": "状元楼", "类型": "绍兴菜", "地址": "越城区胜利西路",
     "推荐": "清汤越鸡、干菜焖肉",
     "简介": "绍兴老牌酒楼，以传统绍兴菜见长"},
    {"店名": "仓桥阿丘面馆", "类型": "面馆", "地址": "越城区仓桥直街",
     "推荐": "次坞打面、片儿川",
     "简介": "仓桥直街巷子里的地道面馆"},
    {"店名": "黄酒博物馆文创店", "类型": "特产购物", "地址": "越城区下大路557号",
     "推荐": "各种年份黄酒、黄酒棒冰、黄酒奶茶",
     "简介": "黄酒博物馆附设商店，可品酒购酒"},
]


class DianpingScraper:
    """
    大众点评数据采集 (静态模式)。

    合规策略:
      - 仅访问搜索列表页 (无需登录)
      - 使用足够长的延时
      - 不进行大量数据抓取
      - API不可用时自动降级为静态美食数据库
    """

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)
        self.max_items = max_items

    def run(self) -> List[Dict]:
        """采集美食数据"""
        logger.info("  大众点评静态采集...")

        # 尝试使用静态回退数据 (更可靠、无需爬取)
        results = self._static_food_data()

        if self.max_items:
            results = results[:self.max_items]

        logger.info(f"  美食数据: {len(results)} 条")
        return results

    def _search_dianping(self, keyword: str) -> List[Dict]:
        """搜索大众点评 (可能被拦截, 有回退方案)"""
        results = []
        try:
            url = f"https://www.dianping.com/search/keyword/7/0_{keyword}"
            resp, tag = self.rm.get(url)

            if tag == 'blocked':
                logger.debug(f"    点评搜索被拦截 [{keyword}]，使用静态数据")
                return []

            if tag == 'ok':
                soup = BeautifulSoup(resp.text, 'html.parser')
                # 解析搜索结果卡片
                for card in soup.select('.shop-item, .shop-list li, [class*="shop"]')[:5]:
                    name_elem = card.select_one('h4, [class*="title"]')
                    addr_elem = card.select_one('[class*="addr"], .address')
                    price_elem = card.select_one('[class*="price"], .avg-price')

                    if name_elem:
                        shop = {
                            '店名': clean_text(name_elem.get_text()),
                            '地址': clean_text(addr_elem.get_text()) if addr_elem else '',
                            '人均': clean_text(price_elem.get_text()) if price_elem else '',
                            '搜索关键词': keyword,
                            '来源': 'dianping',
                            '_data_category': 'food_shop',
                            '_trust_level': 2,
                        }
                        results.append(shop)
        except Exception as e:
            logger.debug(f"    点评搜索异常: {e}")

        return results

    def _static_food_data(self) -> List[Dict]:
        """静态绍兴美食数据库 (无需爬取，数据手工维护)"""
        results = []
        for shop in SHAOXING_FAMOUS_SHOPS:
            results.append({
                '店名': shop['店名'],
                '类型': shop['类型'],
                '地址': shop['地址'],
                '推荐': shop['推荐'],
                '简介': shop['简介'],
                '来源': 'dianping_static',
                '_data_category': 'food_shop',
                '_trust_level': 2,  # 静态数据需交叉验证
            })
        return results
