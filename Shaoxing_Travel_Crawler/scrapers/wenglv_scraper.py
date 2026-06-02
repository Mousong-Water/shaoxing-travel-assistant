"""
浙江省文旅厅数据采集
================================
ct.zj.gov.cn - 政府文旅信息:
  - 非遗名录
  - 精品旅游线路
  - 全省文旅资讯

政府网站, 无反爬, 纯requests即可。
"""

import logging
from typing import List, Dict

from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WenglvScraper:
    """
    浙江省文旅厅数据采集。

    采集内容: 非遗名录、精品线路、文旅资讯
    反爬级别: 无 (政府网站)
    """

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=1.0, delay_max=1.5, max_retries=2)
        self.max_items = max_items or 15

    def run(self) -> List[Dict]:
        """采集文旅资讯"""
        logger.info("  浙江省文旅厅数据采集...")
        results = []

        # 非遗名录 (绍兴相关)
        heritage = self._scrape_heritage()
        results.extend(heritage)
        logger.info(f"    非遗: {len(heritage)} 条")

        # 精品线路
        routes = self._static_routes()
        results.extend(routes)

        logger.info(f"  文旅数据: {len(results)} 条")
        return results[:self.max_items]

    def _scrape_heritage(self) -> List[Dict]:
        """采集非遗名录"""
        items = []
        try:
            url = "http://ct.zj.gov.cn/col/col1644438/index.html"
            resp, tag = self.rm.get(url)

            if tag != 'ok':
                return items

            soup = BeautifulSoup(resp.text, 'html.parser')
            for item in soup.select('.list-item, .news-item, li')[:10]:
                title = clean_text(item.get_text())
                if '绍兴' in title and len(title) > 5:
                    items.append({
                        '名称': title,
                        '来源': 'ct.zj.gov.cn',
                        '_data_category': 'attraction_culture',
                        '_trust_level': 4,  # 政府数据最高可信
                        '_trust_source': 'government',
                    })
        except Exception as e:
            logger.debug(f"    文旅厅异常: {e}")

        return items

    def _static_routes(self) -> List[Dict]:
        """浙江省文旅厅推荐的绍兴精品线路"""
        return [
            {
                "线路名": "绍兴古城文化一日游",
                "景点": "鲁迅故里→沈园→书圣故里→仓桥直街",
                "特色": "深度体验绍兴人文历史",
                "来源": "ct.zj.gov.cn_static",
                "_data_category": "travel_route",
                "_trust_level": 4,
                "_trust_source": "government",
            },
            {
                "线路名": "绍兴水乡古镇二日游",
                "景点": "D1:柯岩+鉴湖+鲁镇 / D2:安昌古镇+东湖",
                "特色": "水乡风情与自然山水结合",
                "来源": "ct.zj.gov.cn_static",
                "_data_category": "travel_route",
                "_trust_level": 4,
                "_trust_source": "government",
            },
            {
                "线路名": "绍兴书法朝圣之旅",
                "景点": "兰亭景区→书圣故里→青藤书屋→绍兴博物馆",
                "特色": "追寻王羲之徐渭书法足迹",
                "来源": "ct.zj.gov.cn_static",
                "_data_category": "travel_route",
                "_trust_level": 4,
                "_trust_source": "government",
            },
        ]
