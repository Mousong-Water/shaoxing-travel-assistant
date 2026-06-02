"""
数据质量验证模块
================================
对清洗后的数据进行完整性检查和评分。
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 关键字段 (必须非空)
REQUIRED_FIELDS = ['name', 'address', 'open_time', 'summary']
# 重要字段 (有则加分)
IMPORTANT_FIELDS = ['ticket_price', 'duration_min', 'rating', 'tags', 'transport_info', 'district']
# 所有评分字段
ALL_FIELDS = REQUIRED_FIELDS + IMPORTANT_FIELDS + ['category', 'season_suitable']


def compute_quality_score(spot: Dict) -> float:
    """
    计算单条数据质量分数 (0-1)。

    规则:
      - 必填字段每缺少一个 -0.15
      - 重要字段每缺少一个 -0.08
      - 评分字段共10个，按权重扣分

    Args:
        spot: 景点数据字典
    Returns:
        质量分数 (0-1)
    """
    score = 1.0

    # 必填字段
    for field in REQUIRED_FIELDS:
        val = spot.get(field)
        if not val or (isinstance(val, str) and len(val) < 2):
            score -= 0.15

    # 重要字段
    for field in IMPORTANT_FIELDS:
        val = spot.get(field)
        if val is None or val == '' or val == 0:
            score -= 0.08

    # 分类
    cat = spot.get('category', '')
    if not cat or cat == '其他' or cat == '':
        score -= 0.05

    return max(0, round(score, 2))


def validate_spot(spot: Dict) -> Dict:
    """
    验证单条数据，标记质量问题。

    Args:
        spot: 景点数据字典
    Returns:
        同一条数据，已添加 data_quality 和 quality_flags 字段
    """
    quality = compute_quality_score(spot)
    spot['data_quality'] = quality

    flags = []

    # 逐字段检查
    if not spot.get('address') or len(spot.get('address', '')) < 3:
        flags.append('MISSING_ADDRESS')

    if not spot.get('open_time'):
        flags.append('MISSING_OPEN_TIME')

    if not spot.get('summary') or len(spot.get('summary', '')) < 10:
        flags.append('MISSING_SUMMARY')

    if not spot.get('ticket_price'):
        flags.append('MISSING_TICKET')

    if not spot.get('duration_min'):
        flags.append('MISSING_DURATION')

    if not spot.get('tags'):
        flags.append('MISSING_TAGS')

    if not spot.get('transport_info'):
        flags.append('MISSING_TRANSPORT')

    if not spot.get('category') or spot.get('category') == '其他':
        flags.append('CATEGORY_UNCERTAIN')

    # 地址噪音检测
    addr = spot.get('address', '')
    if any(w in addr for w in ['讲解', '卫生间', '售票', '参考价格']):
        flags.append('NOISY_ADDRESS')

    # 门票异常检测
    price = spot.get('ticket_price', '')
    ticket_num = spot.get('ticket_numeric')
    if '免费' in price and ticket_num is not None and ticket_num > 0:
        flags.append('TICKET_MISMATCH')

    spot['quality_flags'] = '|'.join(flags) if flags else 'CLEAN'

    if quality < 0.4:
        logger.debug(f"低质量数据 [{spot.get('name', '?')}]: "
                     f"score={quality:.2f}, flags={spot['quality_flags']}")

    return spot


def validate_batch(spots: List[Dict]) -> List[Dict]:
    """
    批量验证数据质量。

    Args:
        spots: 景点数据列表
    Returns:
        已标记质量的景点列表
    """
    validated = []
    for spot in spots:
        try:
            validated.append(validate_spot(spot))
        except Exception as e:
            logger.warning(f"验证失败 [{spot.get('name', '?')}]: {e}")
            # 即使验证失败也返回数据，标记为0分
            spot['data_quality'] = 0.0
            spot['quality_flags'] = 'VALIDATION_ERROR'
            validated.append(spot)

    # 统计
    high = sum(1 for s in validated if s['data_quality'] >= 0.7)
    medium = sum(1 for s in validated if 0.4 <= s['data_quality'] < 0.7)
    low = sum(1 for s in validated if s['data_quality'] < 0.4)
    logger.info(f"质量验证完成: 高={high}, 中={medium}, 低={low} / {len(validated)}")

    return validated


def filter_low_quality(spots: List[Dict], threshold: float = 0.4) -> List[Dict]:
    """
    过滤低质量数据。

    Args:
        spots: 景点数据列表
        threshold: 最低质量阈值 (默认0.4)
    Returns:
        高质量景点列表
    """
    filtered = [s for s in spots if s.get('data_quality', 0) >= threshold]
    logger.info(f"质量过滤: {len(filtered)}/{len(spots)} 条通过 (阈值={threshold})")
    return filtered
