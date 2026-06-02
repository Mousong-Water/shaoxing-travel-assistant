"""
搜狗微信搜索
================================
通过 weixin.sogou.com 搜索绍兴文旅相关公众号文章。
获取: 时令推荐、新店开业、活动资讯、旅游攻略。

合规: 搜狗搜索是公开搜索引擎, 仅搜索公开文章标题和摘要。
"""

import logging
import re
from typing import List, Dict
from urllib.parse import quote

from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 搜索关键词
SEARCH_QUERIES = [
    "绍兴旅游攻略",
    "绍兴美食推荐",
    "绍兴古镇",
    "绍兴赏花",
    "绍兴秋季旅游",
    "绍兴春节活动",
    "绍兴新景点",
    "绍兴周边游",
]


class WeixinSearchScraper:
    """
    搜狗微信搜索采集。

    采集内容: 公众号文章标题、摘要、发布时间
    反爬级别: 低 (搜索引擎, 合理频率即可)
    """

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=2.0, delay_max=3.0, max_retries=2)
        self.max_items = max_items or 20

    def run(self) -> List[Dict]:
        """搜索微信文章"""
        logger.info("  搜狗微信搜索...")
        results = []

        for query in SEARCH_QUERIES:
            if len(results) >= self.max_items:
                break
            articles = self._search(query)
            results.extend(articles)
            logger.info(f"    [{query}] → {len(articles)} 篇")

        logger.info(f"  微信文章: {len(results)} 篇")
        return results[:self.max_items]

    def _search(self, query: str) -> List[Dict]:
        """执行单次搜索"""
        articles = []
        try:
            url = f"https://weixin.sogou.com/weixin?type=2&query={quote(query)}"
            resp, tag = self.rm.get(url)

            if tag != 'ok':
                return articles

            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('.news-item, .news-list li, [class*="item"]')[:3]:
                title_elem = item.select_one('h3 a, [class*="title"] a')
                summary_elem = item.select_one('[class*="summary"], .txt-info, p')
                date_elem = item.select_one('[class*="date"], .time')

                if title_elem:
                    article = {
                        '标题': clean_text(title_elem.get_text()),
                        '链接': title_elem.get('href', ''),
                        '摘要': clean_text(summary_elem.get_text()) if summary_elem else '',
                        '发布时间': clean_text(date_elem.get_text()) if date_elem else '',
                        '搜索词': query,
                        '来源': 'weixin_search',
                        '_data_category': 'seasonal_event',
                        '_trust_level': 1,  # 公众号文章可信度较低
                    }
                    articles.append(article)
        except Exception as e:
            logger.debug(f"    微信搜索异常 [{query}]: {e}")

        return articles


class WeixinStaticGuides:
    """绍兴文旅公众号常见文章主题 (静态参考)"""

    COMMON_TOPICS = [
        {
            "主题": "绍兴春季赏花指南",
            "时间": "每年3-4月",
            "内容摘要": "宛委山樱花、吼山桃花、镜湖湿地油菜花、兰亭竹林",
            "_data_category": "seasonal_event",
        },
        {
            "主题": "绍兴秋季最佳旅游时间",
            "时间": "每年10-11月",
            "内容摘要": "大香林桂花、会稽山红叶、鉴湖桂花节、天姥山秋色",
            "_data_category": "seasonal_event",
        },
        {
            "主题": "绍兴年味·安昌腊月风情节",
            "时间": "每年腊月(12月-1月)",
            "内容摘要": "安昌古镇腊味飘香、传统年俗体验、酱园开缸",
            "_data_category": "seasonal_event",
        },
        {
            "主题": "绍兴必吃十大美食",
            "内容摘要": "臭豆腐、梅干菜扣肉、茴香豆、绍兴黄酒、醉鸡、酱鸭、霉苋菜梗、糟鸡、奶油小攀、次坞打面",
            "_data_category": "local_food",
        },
    ]
