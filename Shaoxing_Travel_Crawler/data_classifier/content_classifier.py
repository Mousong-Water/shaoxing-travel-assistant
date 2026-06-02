"""
内容自动分类器
================================
将采集到的多源数据按内容类型自动归类。

分类体系:
  attraction_basic    - 景点基础信息 (名称/地址/时间/门票)
  attraction_culture  - 文化背景 (历史典故/名人/建筑/非遗)
  attraction_review   - 用户评价 (游记/攻略/心得)
  food_shop           - 美食店铺 (餐厅/小吃店)
  local_food          - 特色小吃 (传统美食/特产)
  seasonal_event      - 时令活动 (节庆/赏花/季节推荐)
  travel_route        - 推荐线路
  official_notice     - 官方公告
  transport_info      - 交通信息
"""

import logging
import re
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

# 分类关键词
CATEGORY_PATTERNS = {
    'attraction_basic': [
        r'(开放时间|门票|地址|游玩时长|评分|评论数)',
    ],
    'attraction_culture': [
        r'(历史|建于|始建于|宋代|明代|清代|典故|传说|名人|书法|文物)',
        r'(保护单位|非遗|申请.*遗产|传统.*工艺)',
    ],
    'attraction_review': [
        r'(推荐|建议|攻略|游记|值得|打卡|必去|好玩)',
        r'(排队|人多|少人|体验|感受|心得)',
    ],
    'food_shop': [
        r'(餐厅|酒店|饭店|面馆|小吃店|酒楼|食府)',
        r'(人均|点菜|菜单|招牌菜|特色菜)',
    ],
    'local_food': [
        r'(臭豆腐|梅干菜|茴香豆|黄酒|醉鸡|酱鸭|糟鸡|霉苋菜)',
        r'(奶油小攀|黄酒奶茶|打面|小笼包|炒年糕|西施豆腐)',
        r'(特产|美食|小吃|推荐菜|必吃)',
    ],
    'seasonal_event': [
        r'(节|活动|展|会|演出|庙会|风情节)',
        r'(赏花|红叶|桂花|樱花|桃花|荷花|梅花|油菜花)',
        r'(春季|夏季|秋季|冬季|每年|月份|时节|时令)',
    ],
    'travel_route': [
        r'(日游|天游|路线|线路|行程|一日|两日|三日)',
        r'(D\d|Day\d|第\d天)',
    ],
    'official_notice': [
        r'(公告|通知|通告|调整|暂停|恢复|维修|关闭)',
        r'(限流|预约|实名|防疫|安全|管理)',
    ],
    'transport_info': [
        r'(公交|地铁|巴士|班车|大巴|高铁|火车|飞机)',
        r'(乘坐|搭乘|到达|交通|出行|怎么去|怎么走)',
    ],
}


class ContentClassifier:
    """内容自动分类器"""

    def classify(self, data: List[Dict]) -> Dict[str, List[Dict]]:
        """
        对数据进行自动分类。

        Args:
            data: 验证后的数据列表
        Returns:
            {category: [items]}
        """
        classified = defaultdict(list)

        for item in data:
            # 先从item自身的_data_category获取
            item_category = item.get('_data_category', '') or item.get('内容分类', '')

            if item_category:
                for cat in item_category.split('|'):
                    cat = cat.strip()
                    if cat:
                        classified[cat].append(item)
            else:
                # 自动推断
                cats = self._infer_categories(item)
                for cat in cats:
                    classified[cat].append(item)

        # 去重 & 统计
        result = {}
        for cat, items in classified.items():
            # 简单去重 (按名称)
            seen = set()
            unique = []
            for item in items:
                name = item.get('名称', item.get('店名', item.get('标题', '')))
                if name and name not in seen:
                    seen.add(name)
                    unique.append(item)
                elif not name:
                    unique.append(item)

            result[cat] = unique
            logger.info(f"  [{cat}]: {len(unique)} 条")

        return result

    def _infer_categories(self, item: Dict) -> List[str]:
        """自动推断数据分类"""
        text = ' '.join(str(v) for v in item.values() if isinstance(v, str))
        scores = {}

        for cat, patterns in CATEGORY_PATTERNS.items():
            score = 0
            for pat in patterns:
                matches = re.findall(pat, text)
                score += len(matches)
            if score > 0:
                scores[cat] = score

        # 返回得分最高的前2个分类
        sorted_cats = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [cat for cat, score in sorted_cats[:2] if score > 0]


class QualityFilter:
    """质量筛选器"""

    @staticmethod
    def filter_by_trust(data: List[Dict], min_trust: int = 2) -> List[Dict]:
        """按信任等级筛选"""
        return [d for d in data if d.get('信任等级', 0) >= min_trust]

    @staticmethod
    def filter_by_source(data: List[Dict], source: str) -> List[Dict]:
        """按数据来源筛选"""
        return [d for d in data if source in d.get('数据来源', '')]

    @staticmethod
    def filter_by_category(data: Dict[str, List[Dict]],
                           categories: List[str]) -> Dict[str, List[Dict]]:
        """按分类筛选"""
        return {k: v for k, v in data.items() if k in categories}

    @staticmethod
    def get_trending(data: List[Dict], top_n: int = 10) -> List[Dict]:
        """获取最热门/最高评分项"""
        sortable = [d for d in data if d.get('评分')]
        try:
            sorted_data = sorted(sortable,
                                 key=lambda x: float(x.get('评分', 0)),
                                 reverse=True)
            return sorted_data[:top_n]
        except (ValueError, TypeError):
            return data[:top_n]
