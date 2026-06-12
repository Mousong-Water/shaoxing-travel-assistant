"""
百度百科采集 (真实requests + 静态回退)
======================================
逐页获取 baike.baidu.com/item/{name}，URL去重，字段统一

合规: 百科为公开知识库、不登录、合理频率(1-2s)
"""

import logging
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

BAIKE_URLS = {
    "鲁迅故里":"https://baike.baidu.com/item/鲁迅故里",
    "沈园":"https://baike.baidu.com/item/沈园",
    "东湖":"https://baike.baidu.com/item/东湖(绍兴)",
    "兰亭景区":"https://baike.baidu.com/item/兰亭",
    "绍兴柯岩风景区":"https://baike.baidu.com/item/柯岩风景区",
    "安昌古镇":"https://baike.baidu.com/item/安昌古镇",
    "大禹陵":"https://baike.baidu.com/item/大禹陵",
    "书圣故里":"https://baike.baidu.com/item/书圣故里",
    "仓桥直街":"https://baike.baidu.com/item/仓桥直街",
    "八字桥":"https://baike.baidu.com/item/八字桥(绍兴)",
    "新昌大佛寺":"https://baike.baidu.com/item/新昌大佛寺",
    "穿岩十九峰":"https://baike.baidu.com/item/穿岩十九峰",
    "五泄风景区":"https://baike.baidu.com/item/五泄",
    "天姥山":"https://baike.baidu.com/item/天姥山",
    "覆卮山":"https://baike.baidu.com/item/覆卮山",
    "西施故里":"https://baike.baidu.com/item/西施故里",
}

FALLBACK = {
    "鲁迅故里":"鲁迅(1881-1936)，中国现代文学奠基人。鲁迅故里是鲁迅诞生和青少年时期生活的地方。《从百草园到三味书屋》以此为背景。全国重点文保。",
    "沈园":"始建于南宋，陆游与前妻唐婉在此重逢写下《钗头凤》。宋代园林风格。全国重点文保。",
    "东湖":"原为汉代采石场，清末陶浚宣筑堤围湖。郭沫若题诗:箬篑东湖，凿自人工。浙江省文保。",
    "兰亭景区":"东晋永和九年(353年)王羲之写下《兰亭序》。曲水流觞典故。全国重点文保。",
    "绍兴柯岩风景区":"汉代始采石，鉴湖建于东汉(公元140年)。柯岩大佛为隋代石刻。全国重点文保(古纤道)。",
}


class BaikeScraper:
    """百度百科采集 (逐页HTTP + 静态回退)"""

    def __init__(self, max_items: int = 30, spot_names: List[str] = None):
        self.rm = RequestManager(delay_min=1.0, delay_max=2.0, max_retries=2)
        self.max_items = max_items
        self.spot_names = spot_names or list(BAIKE_URLS.keys())
        self._seen_urls = set()  # URL去重

    def run(self) -> List[Dict]:
        results = []
        targets = self.spot_names[:self.max_items]
        live_count = 0

        for i, name in enumerate(targets):
            url = BAIKE_URLS.get(name)
            if not url or url in self._seen_urls:
                continue
            self._seen_urls.add(url)

            data = self._scrape_page(name, url)
            if data:
                data["来源平台"] = "baike"
                data["_trust_level"] = 3
                results.append(data)
                live_count += 1
                logger.debug(f"  [{i+1}/{len(targets)}] {name} ← 实时")
                continue

            # 回退
            fb = FALLBACK.get(name)
            if fb:
                results.append({
                    "名称": name,
                    "简介": fb,
                    "来源平台": "baike_fallback",
                    "来源URL": url,
                    "_data_category": "attraction_culture",
                    "_trust_level": 1,
                })
                logger.debug(f"  [{i+1}/{len(targets)}] {name} ← 回退")

        logger.info(f"百科: 实时{live_count}/回退{len(results)-live_count} (共{len(results)}条)")
        return results

    def _scrape_page(self, name: str, url: str) -> Optional[Dict]:
        """真实抓取百科页面"""
        resp, tag = self.rm.get(url)
        if tag != 'ok':
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 摘要
        summary_el = soup.select_one('.lemma-summary, [class*="summary"]')
        summary = clean_text(summary_el.get_text())[:500] if summary_el else ""

        # 正文段落
        paras = []
        for p in soup.select('.para, [class*="content"] p')[:5]:
            text = clean_text(p.get_text())
            if len(text) > 20:
                paras.append(text)

        if not summary and not paras:
            return None

        return {
            "名称": name,
            "简介": summary or " | ".join(paras[:3]),
            "来源URL": url,
            "_data_category": "attraction_culture",
        }
