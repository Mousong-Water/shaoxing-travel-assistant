"""
住宿推荐评分引擎
================================
基于用户偏好+行程景点+真实距离的综合评分。

输入: 用户偏好(预算/风格) + 计划景点列表
输出: 28家住宿按综合得分降序排列

评分权重:
  距离得分 40% — 住宿到计划景点的平均距离
  价格得分 30% — 价格区间与用户预算的匹配度
  风格匹配 20% — 住宿类型与用户偏好的契合度
  评分得分 10% — 住宿本身的口碑评分
"""

import json
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class AccommodationScorer:
    """住宿推荐评分引擎"""

    def __init__(self):
        data_dir = Path(__file__).parent.parent.parent / 'Shaoxing_Travel_Crawler' / 'comprehensive'
        with open(data_dir / 'accommodations.json', 'r', encoding='utf-8') as f:
            self.hotels = json.load(f)
        with open(data_dir / 'attractions.json', 'r', encoding='utf-8') as f:
            self.spots = json.load(f)

    def recommend(
        self,
        planned_spots: List[str],         # 计划游览的景点名称列表
        budget: str = '中等',             # 经济/中等/高端
        style_preference: str = '',       # 古城民宿/高端酒店/温泉/农家乐/不限
        family_mode: bool = False,        # 家庭模式(优先亲子设施)
        top_n: int = 5,                   # 返回前N名
    ) -> List[Dict]:
        """
        推荐住宿。

        Args:
            planned_spots: 计划去的景点名称, 如 ['鲁迅故里','沈园','东湖']
            budget: '经济'(<300元) / '中等'(300-600元) / '高端'(>600元)
            style_preference: 住宿风格偏好, 空字符串=不限
            family_mode: 是否家庭出游(优先亲子房型)
            top_n: 返回前N名

        Returns:
            按综合得分降序排列的推荐列表, 每项含得分明细和推荐理由
        """
        # 获取计划景点的经纬度
        spot_coords = []
        for name in planned_spots:
            coord = self._get_spot_coord(name)
            if coord:
                spot_coords.append(coord)

        if not spot_coords:
            # 无景点坐标时按评分排序
            return sorted(self.hotels, key=lambda h: h.get('rating', 0), reverse=True)[:top_n]

        # 评分
        scored = []
        for hotel in self.hotels:
            dist_score = self._calc_distance_score(hotel, spot_coords)
            price_score = self._calc_price_score(hotel, budget)
            style_score = self._calc_style_score(hotel, style_preference)
            rating_score = self._calc_rating_score(hotel)
            family_bonus = 1.15 if family_mode and self._is_family_friendly(hotel) else 1.0

            total = (dist_score * 0.40 + price_score * 0.30 +
                     style_score * 0.20 + rating_score * 0.10) * family_bonus

            hotel['_score'] = round(total, 3)
            hotel['_score_detail'] = {
                '距离得分': round(dist_score, 2),
                '价格得分': round(price_score, 2),
                '风格得分': round(style_score, 2),
                '评分得分': round(rating_score, 2),
                '家庭加成': family_bonus if family_mode else 1.0,
            }
            hotel['_recommend_reason'] = self._gen_reason(
                hotel, dist_score, price_score, style_score, planned_spots
            )
            scored.append(hotel)

        scored.sort(key=lambda h: h['_score'], reverse=True)
        return scored[:top_n]

    # ---- 评分函数 ----

    def _calc_distance_score(self, hotel: Dict, spot_coords: List[Tuple[float, float]]) -> float:
        """距离得分: 住宿到计划景点平均距离的倒数归一化"""
        h_lat, h_lng = hotel.get('lat'), hotel.get('lng')
        if not h_lat or not h_lng:
            return 0.5  # 无坐标默认中等分

        distances = [self._haversine(h_lat, h_lng, lat, lng) for lat, lng in spot_coords]
        avg_km = sum(distances) / len(distances)

        if avg_km < 1:
            return 1.0
        elif avg_km < 2:
            return 0.9
        elif avg_km < 3:
            return 0.8
        elif avg_km < 5:
            return 0.6
        elif avg_km < 10:
            return 0.4
        else:
            return 0.2

    def _calc_price_score(self, hotel: Dict, budget: str) -> float:
        """价格得分: 价格区间与预算的匹配度"""
        price_range = hotel.get('price_range', '')
        if not price_range:
            return 0.6

        # 提取最低价
        nums = []
        for part in price_range.replace('元', '').split('-'):
            try:
                nums.append(int(part.strip()))
            except ValueError:
                pass
        if not nums:
            return 0.6
        low_price = nums[0]

        budget_map = {'经济': 300, '中等': 600, '高端': 9999}
        threshold = budget_map.get(budget, 600)

        if low_price <= threshold * 0.7:
            return 1.0  # 完全在预算内
        elif low_price <= threshold:
            return 0.8  # 接近预算上限
        elif low_price <= threshold * 1.5:
            return 0.5  # 略超预算
        else:
            return 0.2  # 远超预算

    def _calc_style_score(self, hotel: Dict, preference: str) -> float:
        """风格匹配得分"""
        if not preference:
            return 0.7  # 无偏好默认

        hotel_type = hotel.get('type', '')
        tags = ' '.join(hotel.get('tags', []))

        if preference in hotel_type or preference in tags:
            return 1.0
        if preference == '古城民宿' and '民宿' in hotel_type:
            return 0.9
        if preference == '高端酒店' and '高端' in hotel_type:
            return 0.9
        if preference == '温泉' and '温泉' in hotel_type:
            return 1.0
        if preference == '农家乐' and '农家乐' in hotel_type:
            return 1.0
        return 0.4  # 不匹配

    def _calc_rating_score(self, hotel: Dict) -> float:
        """评分得分: 归一化到0-1"""
        rating = hotel.get('rating', 4.0)
        return min(rating / 5.0, 1.0)

    def _is_family_friendly(self, hotel: Dict) -> bool:
        """判断是否亲子友好"""
        tags = ' '.join(hotel.get('tags', []))
        room_types = ' '.join(hotel.get('room_types', []))
        text = hotel.get('summary', '') + tags + room_types
        return any(w in text for w in ['亲子', '家庭', '儿童', '乐园'])

    def _gen_reason(self, hotel: Dict, dist: float, price: float,
                    style: float, spots: List[str]) -> str:
        """生成推荐理由"""
        reasons = []
        name = hotel['name']
        near = hotel.get('near_spot', '')

        if dist >= 0.8:
            reasons.append(f"距计划景点很近({near})")
        elif dist >= 0.5:
            reasons.append(f"交通便利({near})")

        if price >= 0.8:
            reasons.append(f"价格{hotel.get('price_range','')}预算友好")

        if style >= 0.8:
            reasons.append(f"{hotel.get('type','')}体验")

        if hotel.get('rating', 0) >= 4.5:
            reasons.append(f"口碑优秀({hotel['rating']}分)")

        if not reasons:
            reasons.append(f"综合推荐")

        return '；'.join(reasons)

    # ---- 工具 ----

    def _get_spot_coord(self, name: str) -> Optional[Tuple[float, float]]:
        """根据景点名查找经纬度"""
        for spot in self.spots:
            if spot['name'] == name or name in spot['name'] or spot['name'] in name:
                lat, lng = spot.get('lat'), spot.get('lng')
                if lat and lng:
                    return (lat, lng)
        return None

    @staticmethod
    def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine距离 (km)"""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlng/2)**2)
        return R * 2 * math.asin(math.sqrt(a))

    def suggest_by_area(self, area: str = '越城区', budget: str = '中等') -> List[Dict]:
        """按区域+预算筛选住宿 (不做距离评分, 用于无具体行程时)"""
        matched = [h for h in self.hotels
                   if area in h.get('district', '') or area in h.get('address', '')]
        if not matched:
            matched = self.hotels

        for h in matched:
            price_score = self._calc_price_score(h, budget)
            rating_score = self._calc_rating_score(h)
            h['_score'] = round(price_score * 0.5 + rating_score * 0.5, 3)
            h['_recommend_reason'] = self._gen_reason(h, 0.5, price_score, 0.5, [])

        matched.sort(key=lambda h: h['_score'], reverse=True)
        return matched[:8]

    @staticmethod
    def general_advice(planned_spots: List[str], budget: str = '中等') -> str:
        """生成通用的自行挑选住宿建议 (无具体推荐时)"""
        area_hint = "越城区" if any(s in str(planned_spots)
                    for s in ['鲁迅','沈园','书圣','仓桥','八字桥','东湖']) else "各景点附近"
        budget_hint = {
            '经济': '150-300元的经济酒店或青旅，鲁迅故里周边选择多',
            '中等': '300-600元的舒适型酒店或精品民宿，仓桥直街和书圣故里附近最佳',
            '高端': '500-1200元的高端度假酒店，推荐绍兴饭店或大禹开元观堂',
        }.get(budget, '中等价位的酒店或民宿')

        return (
            f"建议住在{area_hint}，{budget_hint}。"
            f"越城区景点集中，住在鲁迅故里-仓桥直街一带步行可达大部分景点。"
            f"如果去柯岩/安昌方向较多，可考虑柯桥区住宿性价比更高。"
            f"预订前建议查看近期住客评价，旺季(3-5月/9-10月)提前1-2周预订。"
        )


# ============================================================
# 快速测试
# ============================================================
if __name__ == '__main__':
    scorer = AccommodationScorer()

    # 场景1: 文化一日游 + 中等预算 + 古城民宿偏好
    print("=== 场景1: 鲁迅故里+沈园+书圣故里 | 中等预算 | 民宿偏好 ===")
    results = scorer.recommend(
        ['鲁迅故里', '沈园', '书圣故里'],
        budget='中等',
        style_preference='古城民宿',
        top_n=5,
    )
    for i, h in enumerate(results):
        print(f"  {i+1}. {h['name']} | {h.get('_score')}分 | {h.get('_recommend_reason')}")

    # 场景2: 家庭出游 + 柯岩+安昌
    print("\n=== 场景2: 柯岩+安昌古镇 | 家庭模式 | 中等预算 ===")
    results = scorer.recommend(
        ['绍兴柯岩风景区', '安昌古镇'],
        budget='中等',
        family_mode=True,
        top_n=5,
    )
    for i, h in enumerate(results):
        print(f"  {i+1}. {h['name']} | {h.get('_score')}分 | {h.get('_recommend_reason')}")

    # 场景3: 无具体行程时的通用建议
    print("\n=== 场景3: 通用建议 ===")
    print(scorer.general_advice(['鲁迅故里', '东湖'], budget='中等'))
