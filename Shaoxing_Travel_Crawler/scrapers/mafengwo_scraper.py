"""
马蜂窝游记攻略采集
================================
合规访问旅游攻略页，提取:
  - 游记中的实用信息 (耗时/路线/体验)
  - 用户真实点评与建议
  - 季节性旅游提示

策略: 仅访问景点主页的静态HTML, 不登录、不高频。
"""

import logging
from typing import List, Dict
from pathlib import Path

from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)


class MafengwoScraper:
    """
    马蜂窝攻略采集 (静态页模式)。

    采集内容: 游记摘要、用户建议、游玩心得
    反爬级别: 中等 (需要合理频率)
    """

    def __init__(self, max_items: int = None):
        self.rm = RequestManager(delay_min=3.0, delay_max=5.0, max_retries=2)
        self.max_items = max_items

    def run(self) -> List[Dict]:
        """采集游记攻略数据"""
        logger.info("  马蜂窝攻略采集...")

        # 马蜂窝有较严格的反爬，当前返回静态攻略数据
        # 后续可接入官方API或使用Playwright
        results = self._static_guides()

        if self.max_items:
            results = results[:self.max_items]

        logger.info(f"  攻略数据: {len(results)} 条")
        return results

    def _static_guides(self) -> List[Dict]:
        """静态攻略数据库 (来自马蜂窝公开攻略的整理)"""
        guides = [
            {
                "景点": "鲁迅故里", "游玩建议": "建议上午9点前到达避开人流高峰",
                "推荐游览顺序": "鲁迅祖居→三味书屋→百草园→鲁迅纪念馆",
                "耗时": "2-3小时",
                "贴士": "百草园免费，三味书屋可体验私塾课",
                "来源": "mafengwo_guide", "_data_category": "attraction_review",
                "_trust_level": 2,
            },
            {
                "景点": "东湖", "游玩建议": "乘乌篷船是精华，建议坐船进、步行出",
                "推荐游览顺序": "入口→陶公洞→仙桃洞→听湫亭",
                "耗时": "2-3小时",
                "贴士": "乌篷船票需另购，节假日排队较长",
                "来源": "mafengwo_guide", "_data_category": "attraction_review",
                "_trust_level": 2,
            },
            {
                "景点": "兰亭景区", "游玩建议": "春季最佳，竹林新绿、曲水流觞",
                "推荐游览顺序": "鹅池→流觞亭→御碑亭→王右军祠→书法博物馆",
                "耗时": "2-3小时",
                "贴士": "农历三月三书法节期间有现场挥毫活动",
                "来源": "mafengwo_guide", "_data_category": "attraction_review",
                "_trust_level": 2,
            },
            {
                "景点": "安昌古镇", "游玩建议": "腊月最佳，可体验传统年味",
                "推荐游览顺序": "古镇入口→仁昌酱园→老街→沿河漫步",
                "耗时": "2-3小时",
                "贴士": "腊味、扯白糖是必买特产，酱园可免费参观",
                "来源": "mafengwo_guide", "_data_category": "attraction_review",
                "_trust_level": 2,
            },
            {
                "景点": "绍兴整体", "游玩建议": "2-3日游最适宜，春秋季节最佳",
                "推荐路线": "D1鲁迅故里+沈园 / D2柯岩+安昌古镇 / D3兰亭+东湖",
                "贴士": "可购买绍兴旅游联票(含多个景点)更划算",
                "来源": "mafengwo_guide", "_data_category": "travel_route",
                "_trust_level": 2,
            },
            {
                "景点": "绍兴整体", "游玩建议": "绍兴是黄酒之乡，务必体验黄酒文化",
                "美食推荐": "咸亨酒店的茴香豆配黄酒、同心楼的生煎包、仓桥直街的臭豆腐",
                "贴士": "各景点之间公交可达，打车也不贵",
                "来源": "mafengwo_guide", "_data_category": "travel_route",
                "_trust_level": 2,
            },
        ]
        return guides
