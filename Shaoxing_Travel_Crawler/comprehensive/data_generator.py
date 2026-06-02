"""
综合数据生成器
================================
将结构化实体数据展开为多维度数据条目。

策略: 1个实体 → 5~8条多维度记录
  景点 → basic + culture + review + seasonal + transport
  美食 → shop + dish + area
  文化 → culture + event + heritage

目标产出: 800~1500条
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent


def load_json(filename: str) -> List[Dict]:
    """加载JSON数据文件"""
    path = _DATA_DIR / filename
    if not path.exists():
        logger.warning(f"数据文件不存在: {path}")
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


class DataGenerator:
    """
    多维度数据生成器。

    输入: 结构化实体JSON
    输出: 展开后的多维度记录字典
    """

    def __init__(self):
        self.attractions = load_json('attractions.json')
        self.foods = load_json('foods.json')
        self.cultures = load_json('cultures.json')
        self.routes = load_json('routes.json')
        self.events = load_json('events.json')

    def generate_all(self) -> Dict[str, List[Dict]]:
        """生成全部数据"""
        results = {
            'attraction_basic': [],
            'attraction_culture': [],
            'attraction_review': [],
            'food_shop': [],
            'local_food': [],
            'seasonal_event': [],
            'travel_route': [],
            'official_notice': [],
            'transport_info': [],
        }

        # 景点 → 5维度
        for a in self.attractions:
            results['attraction_basic'].append(self._gen_basic(a))
            results['attraction_culture'].append(self._gen_culture(a))
            results['attraction_review'].append(self._gen_review(a))
            results['transport_info'].append(self._gen_transport(a))
            # 有季节信息的额外生成活动条目
            if a.get('best_season') or a.get('seasonal_event'):
                results['seasonal_event'].append(self._gen_seasonal(a))

        # 美食 → 2维度 (店铺 + 菜品)
        for f in self.foods:
            results['food_shop'].append(self._gen_shop(f))
            for dish in f.get('signature_dishes', [])[:3]:
                results['local_food'].append(self._gen_dish(f, dish))

        # 文化 → 2维度
        for c in self.cultures:
            entry = self._gen_heritage(c)
            results['attraction_culture'].append(entry)
            if c.get('festival_date'):
                results['seasonal_event'].append(self._gen_cultural_event(c))

        # 路线
        for r in self.routes:
            results['travel_route'].append(r)

        # 活动
        for e in self.events:
            results['seasonal_event'].append(e)

        # 统计
        total = sum(len(v) for v in results.values())
        logger.info(f"数据生成完成: {total} 条 "
                    f"(景点{len(self.attractions)}→{len(results['attraction_basic'])*2}维, "
                    f"美食{len(self.foods)}→{len(results['food_shop'])+len(results['local_food'])}条, "
                    f"文化{len(self.cultures)})")
        return results

    # ---- 景点各维度生成 ----

    def _gen_basic(self, a: Dict) -> Dict:
        return {
            '名称': a['name'], '行政区': a.get('district', ''),
            '地址': a.get('address', ''),
            '开放时间': a.get('open_time', ''), '门票价格': a.get('ticket', ''),
            '评分': a.get('rating', 4.0), '评论数': a.get('reviews', 0),
            '标签': '|'.join(a.get('tags', [])),
            '简介': a.get('summary', ''), '分类': a.get('category', ''),
            '适宜季节': a.get('best_season', ''),
            '图片URL': '|'.join(a.get('image_urls', [])),
            '纬度': a.get('lat'), '经度': a.get('lng'),
            '来源URL': f"comprehensive:attraction:{a['name']}",
            '来源平台': 'comprehensive', '信任等级': 3,
            '_data_category': 'attraction_basic',
        }

    def _gen_culture(self, a: Dict) -> Dict:
        culture = a.get('culture', {})
        return {
            '名称': a['name'],
            '历史背景': culture.get('history', ''),
            '建造年代': culture.get('era', ''),
            '文化典故': culture.get('story', ''),
            '建筑特色': culture.get('architecture', ''),
            '保护级别': culture.get('heritage_level', ''),
            '简介': f"{culture.get('history','')} {culture.get('story','')}",
            '来源URL': f"comprehensive:culture:{a['name']}",
            '来源平台': 'comprehensive', '信任等级': 3,
            '_data_category': 'attraction_culture',
        }

    def _gen_review(self, a: Dict) -> Dict:
        tips = a.get('visit_tips', {})
        return {
            '景点': a['name'],
            '游玩建议': tips.get('advice', ''),
            '推荐游览顺序': tips.get('route', ''),
            '耗时': tips.get('duration', ''),
            '最佳季节': tips.get('best_time', a.get('best_season', '')),
            '贴士': tips.get('tips', ''),
            '来源URL': f"comprehensive:review:{a['name']}",
            '来源平台': 'comprehensive', '信任等级': 2,
            '_data_category': 'attraction_review',
        }

    def _gen_transport(self, a: Dict) -> Dict:
        transport = a.get('transport', '')
        return {
            '名称': a['name'],
            '交通': transport,
            '内容': f"前往{a['name']}: {transport}",
            '来源URL': f"comprehensive:transport:{a['name']}",
            '来源平台': 'comprehensive', '信任等级': 2,
            '_data_category': 'transport_info',
        }

    def _gen_seasonal(self, a: Dict) -> Dict:
        event = a.get('seasonal_event', {})
        return {
            '主题': event.get('name', f"{a['name']}最佳游览季"),
            '时间': event.get('time', a.get('best_season', '')),
            '内容摘要': event.get('desc', ''),
            '景点': a['name'],
            '来源URL': f"comprehensive:seasonal:{a['name']}",
            '来源平台': 'comprehensive', '信任等级': 2,
            '_data_category': 'seasonal_event',
        }

    # ---- 美食各维度生成 ----

    def _gen_shop(self, f: Dict) -> Dict:
        return {
            '店名': f['name'], '类型': f.get('category', ''),
            '地址': f.get('address', ''), '人均': f.get('avg_price', ''),
            '推荐': '、'.join(f.get('signature_dishes', [])),
            '简介': f.get('description', ''),
            '来源URL': f"comprehensive:food:{f['name']}",
            '来源平台': 'comprehensive', '信任等级': 2,
            '_data_category': 'food_shop',
        }

    def _gen_dish(self, f: Dict, dish: str) -> Dict:
        return {
            '名称': dish,
            '分类': f.get('dish_category', f.get('category', '')),
            '所属店铺': f['name'],
            '简介': f"{dish}——{f.get('description','')[:60]}",
            '来源URL': f"comprehensive:dish:{dish}",
            '来源平台': 'comprehensive', '信任等级': 2,
            '_data_category': 'local_food',
        }

    # ---- 文化各维度生成 ----

    def _gen_heritage(self, c: Dict) -> Dict:
        return {
            '名称': c['name'],
            '文化类型': c.get('type', ''),
            '级别': c.get('level', ''),
            '历史背景': c.get('history', ''),
            '文化典故': c.get('description', ''),
            '保护现状': c.get('status', ''),
            '简介': c.get('description', ''),
            '来源URL': f"comprehensive:culture:{c['name']}",
            '来源平台': 'comprehensive', '信任等级': 3,
            '_data_category': 'attraction_culture',
        }

    def _gen_cultural_event(self, c: Dict) -> Dict:
        return {
            '主题': c.get('festival_name', c['name']),
            '时间': c.get('festival_date', ''),
            '内容摘要': c.get('festival_desc', c.get('description', '')),
            '文化项目': c['name'],
            '来源URL': f"comprehensive:event:{c['name']}",
            '来源平台': 'comprehensive', '信任等级': 3,
            '_data_category': 'seasonal_event',
        }
