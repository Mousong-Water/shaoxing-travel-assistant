"""
百度百科爬虫
================================
获取景点历史文化背景、建筑特色、名人典故。
反爬极低，纯requests即可。

使用: baike.baidu.com/item/{景点名}
"""

import logging
import re
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper, make_empty_spot
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

# 绍兴已知景点百度百科URL
SHAOXING_BAIKE_URLS = {
    "鲁迅故里": "https://baike.baidu.com/item/鲁迅故里",
    "沈园": "https://baike.baidu.com/item/沈园",
    "东湖": "https://baike.baidu.com/item/东湖(绍兴)",
    "兰亭": "https://baike.baidu.com/item/兰亭",
    "柯岩风景区": "https://baike.baidu.com/item/柯岩风景区",
    "安昌古镇": "https://baike.baidu.com/item/安昌古镇",
    "大禹陵": "https://baike.baidu.com/item/大禹陵",
    "新昌大佛寺": "https://baike.baidu.com/item/新昌大佛寺",
    "五泄": "https://baike.baidu.com/item/五泄",
    "穿岩十九峰": "https://baike.baidu.com/item/穿岩十九峰",
    "书圣故里": "https://baike.baidu.com/item/书圣故里",
    "仓桥直街": "https://baike.baidu.com/item/仓桥直街",
    "八字桥": "https://baike.baidu.com/item/八字桥(绍兴)",
    "覆卮山": "https://baike.baidu.com/item/覆卮山",
    "天姥山": "https://baike.baidu.com/item/天姥山",
    "西施故里": "https://baike.baidu.com/item/西施故里",
    "曹娥庙": "https://baike.baidu.com/item/曹娥庙",
    "崇仁古镇": "https://baike.baidu.com/item/崇仁古镇",
    "绍兴博物馆": "https://baike.baidu.com/item/绍兴博物馆",
    "青藤书屋": "https://baike.baidu.com/item/青藤书屋",
    "秋瑾故居": "https://baike.baidu.com/item/秋瑾故居",
    "周恩来祖居": "https://baike.baidu.com/item/周恩来祖居",
    "蔡元培故居": "https://baike.baidu.com/item/蔡元培故居",
}


class BaikeScraper:
    """
    百度百科数据采集。

    提取内容:
      - 历史背景 / 建造年代
      - 文化典故 / 名人关联
      - 建筑特色 / 规模
      - 保护级别 (国保/省保)
    """

    def __init__(self, max_items: int = None, spot_names: List[str] = None):
        self.rm = RequestManager(delay_min=1.0, delay_max=2.0, max_retries=2)
        self.max_items = max_items
        # 可指定景点列表，默认使用已知URL
        self.spot_names = spot_names or list(SHAOXING_BAIKE_URLS.keys())

    def run(self) -> List[Dict]:
        """采集百度百科数据"""
        results = []
        targets = self.spot_names[:self.max_items] if self.max_items else self.spot_names

        for i, name in enumerate(targets):
            url = SHAOXING_BAIKE_URLS.get(name)
            if not url:
                continue

            logger.info(f"  [{i+1}/{len(targets)}] 百度百科: {name}")
            try:
                data = self._scrape_baike(name, url)
                if data:
                    results.append(data)
            except Exception as e:
                logger.warning(f"    百度百科失败 [{name}]: {e}")

        logger.info(f"百度百科采集完成: {len(results)} 条")
        return results

    def _scrape_baike(self, name: str, url: str) -> Optional[Dict]:
        """爬取单个百度百科页面"""
        resp, tag = self.rm.get(url)
        if tag != 'ok':
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        spot = make_empty_spot(name=name, city='绍兴',
                               url=f"baike_import:{name}", platform='baike')

        # 1. 摘要 (class="lemma-summary")
        summary_elem = soup.select_one('.lemma-summary, [class*="summary"]')
        if summary_elem:
            spot['简介'] = clean_text(summary_elem.get_text())[:500]

        # 2. 基本信息 (从infobox提取)
        info_box = soup.select_one('.basicInfo-item, .infobox')
        if info_box:
            lines = clean_text(info_box.get_text())
            # 尝试提取开放时间、门票、地址
            for line in lines.split(' '):
                line = line.strip()
                if '时间' in line and not spot['开放时间']:
                    spot['开放时间'] = line
                elif '门票' in line and not spot['门票价格']:
                    spot['门票价格'] = line
                elif '地址' in line and not spot['地址']:
                    spot['地址'] = line.replace('地址', '').strip()

        # 3. 正文提取 (历史/文化段落)
        content_paras = []
        for p in soup.select('.para, [class*="content"] p'):
            text = clean_text(p.get_text())
            if len(text) > 20:
                content_paras.append(text)
            if len(content_paras) >= 5:  # 最多5段
                break

        if content_paras:
            spot['_cultural_content'] = '\n'.join(content_paras)

        # 4. 分类标记
        full_text = soup.get_text()
        if '文物保护' in full_text or '重点文物' in full_text:
            spot['_heritage_level'] = '全国重点文物保护单位'
        elif '省保' in full_text:
            spot['_heritage_level'] = '省级文物保护单位'

        # 5. 可信度标记
        spot['_trust_source'] = 'encyclopedia'
        spot['_trust_level'] = 3  # 百科数据较可信
        spot['_data_category'] = 'attraction_culture'

        return spot
