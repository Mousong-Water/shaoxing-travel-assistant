"""
百度百科采集 (真实requests + 静态回退)
======================================
策略: 访问 baike.baidu.com/item/{景点名} 提取文化背景信息
URL: https://baike.baidu.com/item/{name}

合规: 百科为公开知识库、不登录、合理频率(1-2s)
"""

import logging
import re
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from crawler_utils.request_utils import RequestManager
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

# 景点→百科URL
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

# 静态回退 (15个景点文化背景)
CULTURE_FALLBACK = {
    "鲁迅故里":{"历史背景":"鲁迅(1881-1936)，中国现代文学奠基人。鲁迅故里是鲁迅诞生和青少年时期生活的地方。","建造年代":"清代建筑","文化典故":"《从百草园到三味书屋》《故乡》等名篇以此为背景","保护级别":"全国重点文物保护单位"},
    "沈园":{"历史背景":"始建于南宋，陆游与前妻唐婉在此重逢写下《钗头凤》。","建造年代":"南宋(约1151年)","文化典故":"陆游《钗头凤》:红酥手，黄縢酒，满城春色宫墙柳","保护级别":"全国重点文物保护单位"},
    "东湖":{"历史背景":"原为汉代采石场，清末陶浚宣筑堤围湖建成山水大盆景。","建造年代":"汉代始采石，1899年建为园林","文化典故":"郭沫若题诗:箬篑东湖，凿自人工","保护级别":"浙江省文物保护单位"},
    "兰亭景区":{"历史背景":"东晋永和九年(353年)，王羲之在此写下天下第一行书《兰亭序》。","建造年代":"汉代始建，现存建筑明清重修","文化典故":"曲水流觞、鹅池碑为王羲之王献之父子合书","保护级别":"全国重点文物保护单位"},
    "绍兴柯岩风景区":{"历史背景":"柯岩始于汉代采石，鉴湖为东汉马臻修建的水利工程。","建造年代":"汉代始采石，鉴湖建于公元140年","文化典故":"柯岩大佛为隋代石刻，云骨被誉为天下第一石","保护级别":"全国重点文物保护单位(古纤道)"},
}


class BaikeScraper:
    """百度百科采集 (真实HTTP + 静态回退)"""

    def __init__(self, max_items: int = None, spot_names: List[str] = None):
        self.rm = RequestManager(delay_min=1.0, delay_max=2.0, max_retries=2)
        self.max_items = max_items or 30
        self.spot_names = spot_names or list(BAIKE_URLS.keys())

    def run(self) -> List[Dict]:
        results = []
        targets = self.spot_names[:self.max_items]

        # 1. 真实抓取
        for i, name in enumerate(targets):
            url = BAIKE_URLS.get(name)
            if not url:
                continue
            try:
                data = self._scrape_baike_page(name, url)
                if data:
                    results.append(data)
                    logger.debug(f"  [{i+1}/{len(targets)}] {name} ← 实时")
                    continue
            except Exception as e:
                logger.debug(f"  百科[{name}]: {e}")

            # 2. 回退
            fb = CULTURE_FALLBACK.get(name)
            if fb:
                results.append(self._fallback_item(name, fb))
                logger.debug(f"  [{i+1}/{len(targets)}] {name} ← 回退")

        live_count = sum(1 for r in results if r.get("来源平台") == "baike")
        logger.info(f"百科: 实时{live_count}/回退{len(results)-live_count} (共{len(results)}条)")
        return results

    def _scrape_baike_page(self, name: str, url: str) -> Optional[Dict]:
        """真实抓取百科页面"""
        resp, tag = self.rm.get(url)
        if tag != 'ok':
            return None

        soup = BeautifulSoup(resp.text, 'html.parser')

        # 摘要
        summary = ""
        summary_el = soup.select_one('.lemma-summary, [class*="summary"]')
        if summary_el:
            summary = clean_text(summary_el.get_text())[:500]

        # 基本信息
        info = {}
        for item in soup.select('.basicInfo-item'):
            key_el = item.select_one('.item-name')
            val_el = item.select_one('.item-value')
            if key_el and val_el:
                key = clean_text(key_el.get_text())
                val = clean_text(val_el.get_text())
                info[key] = val

        if not summary and not info:
            return None  # 页面为空，回退

        # 正文段落
        paras = []
        for p in soup.select('.para, [class*="content"] p')[:5]:
            text = clean_text(p.get_text())
            if len(text) > 20:
                paras.append(text)

        return {
            "名称": name,
            "简介": summary or "|".join(paras[:3]),
            "历史背景": info.get("中文名", ""),
            "建造年代": info.get("始建时间", ""),
            "保护级别": info.get("保护级别", ""),
            "文化典故": " | ".join(paras[:2]) if paras else "",
            "来源平台": "baike",
            "来源URL": url,
            "_data_category": "attraction_culture",
            "_trust_level": 3,  # 百科数据较可信
        }

    def _fallback_item(self, name: str, fb: dict) -> Dict:
        return {
            "名称": name,
            "简介": f"{fb.get('历史背景','')} | {fb.get('文化典故','')}",
            "历史背景": fb.get("历史背景", ""),
            "建造年代": fb.get("建造年代", ""),
            "文化典故": fb.get("文化典故", ""),
            "保护级别": fb.get("保护级别", ""),
            "来源平台": "baike_fallback",
            "来源URL": f"baike_static:{name}",
            "_data_category": "attraction_culture",
            "_trust_level": 1,  # 回退数据信任度低
        }
