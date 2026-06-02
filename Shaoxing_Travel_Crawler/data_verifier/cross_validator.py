"""
多源交叉验证引擎
================================
核心理念: 同一信息在多个数据源中出现 → 可信度更高。

验证规则:
  Level 4 (权威)  : 政府/官方数据源确认
  Level 3 (高可信): 3个及以上独立来源一致
  Level 2 (较可信): 2个独立来源一致
  Level 1 (仅参考): 单一来源
  Level 0 (不可信): 被其他来源证伪

解决比赛要求:
  "核实数据的真实性，做到真实可信避免出现ai幻觉"
  "对同一个景点，可以寻找近几年的数据，作为知识参考"
"""

import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class CrossValidator:
    """
    多源交叉验证器。

    验证维度:
      1. 基础字段可信度 (名称/地址/门票/时间)
      2. 多源一致性打分
      3. 冲突检测与标记
      4. 历史数据追踪
    """

    def __init__(self):
        self.trust_scores = {
            'government': 4,      # 政府数据
            'encyclopedia': 3,    # 百科
            'official_site': 3,   # 景区官网
            'news': 2,            # 新闻媒体
            'platform': 2,        # 旅游平台
            'ugc': 1,             # 用户生成内容
            'social_media': 1,    # 社交媒体
        }

    def validate(self, raw_results: Dict[str, List[Dict]]) -> List[Dict]:
        """
        多源交叉验证。

        Args:
            raw_results: {source_key: [data_dict, ...]}
        Returns:
            合并验证后的数据列表，每项带信任标记
        """
        # Step 1: 按景点名称归并
        merged = self._merge_by_name(raw_results)

        # Step 2: 逐景点交叉验证
        verified = []
        for name, sources in merged.items():
            record = self._cross_validate_spot(name, sources)
            if record:
                verified.append(record)

        # Step 3: 信任度统计
        trust_dist = defaultdict(int)
        for r in verified:
            trust_dist[r.get('信任等级', 0)] += 1

        logger.info(f"交叉验证完成: {len(verified)} 条")
        logger.info(f"  信任分布: L4={trust_dist[4]} L3={trust_dist[3]} "
                    f"L2={trust_dist[2]} L1={trust_dist[1]}")

        return verified

    def _merge_by_name(self, raw: Dict[str, List[Dict]]) -> Dict[str, Dict[str, List[Dict]]]:
        """按景点名称归并多源数据"""
        merged = defaultdict(lambda: defaultdict(list))

        for source_key, items in raw.items():
            for item in items:
                name = self._normalize_name(
                    item.get('名称', '') or
                    item.get('店名', '') or
                    item.get('name', '')
                )
                if not name or len(name) < 2:
                    continue
                merged[name][source_key].append(item)

        return dict(merged)

    def _normalize_name(self, name: str) -> str:
        """名称标准化: 去除括号、空格等干扰"""
        import re
        name = name.strip()
        # 去除括号注释: "东湖(绍兴)" → "东湖"
        name = re.sub(r'[（(][^)）]*[)）]', '', name)
        return name

    def _cross_validate_spot(self, name: str, sources: Dict[str, List[Dict]]) -> Optional[Dict]:
        """
        对单个景点进行交叉验证。

        返回合并后的数据, 包含:
          - 各字段的最可信值
          - 信任等级
          - 来源列表
          - 冲突标记
        """
        num_sources = len(sources)
        source_list = list(sources.keys())
        all_items = []
        for items in sources.values():
            all_items.extend(items)

        # 1. 提取各字段的值及来源
        fields = {
            '地址': self._collect_field(all_items, '地址'),
            '开放时间': self._collect_field(all_items, '开放时间'),
            '门票价格': self._collect_field(all_items, '门票价格'),
            '评分': self._collect_field(all_items, '评分'),
            '简介': self._collect_field(all_items, '简介'),
            '游玩时长': self._collect_field(all_items, '游玩时长'),
        }

        # 2. 每字段选最可信值
        verified = {
            '名称': name,
            '数据来源': '|'.join(source_list),
            '来源数量': num_sources,
        }

        for field, candidates in fields.items():
            if candidates:
                best = self._select_best_value(candidates)
                verified[field] = best['value']
                if best['conflict']:
                    verified[f'{field}_可信度'] = '有冲突'
                    verified[f'{field}_备选值'] = best['alternatives']
            else:
                verified[field] = ''

        # 3. 计算综合信任等级
        base_trust = self._compute_trust_level(sources, all_items)
        verified['信任等级'] = base_trust

        # 4. 历史数据标记 (如有)
        timestamps = [item.get('_timestamp', '') for item in all_items if item.get('_timestamp')]
        if timestamps:
            verified['数据时间范围'] = f"{min(timestamps)} ~ {max(timestamps)}"
            verified['数据年份数'] = len(set(t.split('-')[0] for t in timestamps if t))

        # 5. 分类信息
        categories = set()
        for item in all_items:
            cat = item.get('_data_category', '')
            if cat:
                categories.add(cat)
        verified['内容分类'] = '|'.join(categories) if categories else ''

        # 6. 来源信息
        verified['来源详情'] = {
            k: len(v) for k, v in sources.items()
        }

        return verified

    def _collect_field(self, items: List[Dict], field: str) -> List[Dict]:
        """收集某字段的所有候选值及来源"""
        candidates = []
        for item in items:
            value = item.get(field, '') or item.get(f'_{field}', '')
            if value and str(value).strip():
                candidates.append({
                    'value': str(value).strip(),
                    'source': item.get('来源', item.get('_source', 'unknown')),
                    'trust': item.get('_trust_level', 1),
                    'platform': item.get('来源平台', item.get('来源', '')),
                })
        return candidates

    def _select_best_value(self, candidates: List[Dict]) -> Dict:
        """
        从候选中选择最佳值。

        策略:
          1. 政府数据优先
          2. 已有trust_level的记录优先
          3. 多源一致的值优先
          4. 出现最多的值优先
        """
        if not candidates:
            return {'value': '', 'conflict': False, 'alternatives': []}

        # 按信任度排序
        sorted_candidates = sorted(candidates, key=lambda x: x['trust'], reverse=True)

        # 检查一致性
        values = [c['value'] for c in sorted_candidates]
        unique_values = list(set(values))

        if len(unique_values) == 1:
            # 所有源一致 - 高可信
            return {
                'value': sorted_candidates[0]['value'],
                'conflict': False,
                'alternatives': [],
                'consensus': True,
            }
        elif len(unique_values) <= 3:
            # 少数不一致 - 取多数
            from collections import Counter
            most_common = Counter(values).most_common(1)[0][0]
            others = [v for v in unique_values if v != most_common]
            return {
                'value': most_common,
                'conflict': True,
                'alternatives': others[:3],
                'consensus': False,
            }
        else:
            # 严重不一致 - 取最高信任源的值
            return {
                'value': sorted_candidates[0]['value'],
                'conflict': True,
                'alternatives': unique_values[1:5],
                'consensus': False,
            }

    def _compute_trust_level(self, sources: Dict[str, List[Dict]],
                             all_items: List[Dict]) -> int:
        """
        计算综合信任等级。

        规则:
          - 有政府数据 → 最低3级
          - 3+独立源一致 → 3级
          - 2源一致 → 2级
          - 单源 → 1级
          - 单源且标记可信 → 可升1级
        """
        num_sources = len(sources)
        has_gov = any('gov' in k or 'wenglv' in k for k in sources.keys())
        has_encyclopedia = any('baike' in k for k in sources.keys())
        max_item_trust = max((item.get('_trust_level', 1) for item in all_items), default=1)

        if has_gov:
            return max(4, max_item_trust)  # 政府数据保证至少4级
        if num_sources >= 3:
            return 3
        if num_sources == 2:
            return 2
        if has_encyclopedia:
            return min(2, max_item_trust)  # 百科数据至少2级
        return max(1, max_item_trust)


class FactChecker:
    """事实检查器 - 检测明显错误或自相矛盾的数据"""

    @staticmethod
    def check_spot_data(spot: Dict) -> List[str]:
        """
        检查单个景点数据的问题。

        Returns:
            问题描述列表 (空列表=无问题)
        """
        issues = []

        # 门票价格合理性
        ticket = spot.get('门票价格', '')
        if '免费' in str(ticket) and spot.get('等级') in ['5A', '4A']:
            issues.append(f"[门票] {spot.get('名称','')} 标注免费但为高等级景区，请核实")

        # 评分范围
        try:
            rating = float(spot.get('评分', 0))
            if rating > 6 or rating < 0:
                issues.append(f"[评分] 评分{rating}超出正常范围(0-5)")
        except (ValueError, TypeError):
            pass

        # 地址与行政区一致性
        addr = spot.get('地址', '')
        district = spot.get('行政区', '')
        if district and addr:
            if district not in addr:
                issues.append(f"[地址] 行政区'{district}'与地址'{addr[:30]}'不一致")

        # 时间格式
        open_time = spot.get('开放时间', '')
        if open_time and ':' not in open_time and open_time not in ['全天开放', '全天']:
            issues.append(f"[时间] 开放时间'{open_time}'格式异常")

        return issues
