"""
补充数据采集
================================
从额外数据源获取景点补充信息:
  - 季节性活动 (来自本地JSON配置)
  - 百度百科简介 (预留接口)
  - 地理位置信息 (预留接口)
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from data_layer.storage.db_manager import DBManager

logger = logging.getLogger(__name__)

# 季节性数据文件路径
_SEASONAL_DATA_PATH = Path(__file__).parent / "seasonal_data.json"


# ============================================================
# 季节性活动补充
# ============================================================

def load_seasonal_data() -> dict:
    """加载季节性活动数据"""
    if not _SEASONAL_DATA_PATH.exists():
        logger.warning(f"季节性数据文件不存在: {_SEASONAL_DATA_PATH}")
        return {}
    with open(_SEASONAL_DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def enrich_seasonal_info(db: DBManager) -> int:
    """
    将季节性活动数据写入seasonal_info表。

    匹配策略: 按景点名称模糊匹配 attractions 表。

    Returns:
        写入的季节信息条数
    """
    seasonal_data = load_seasonal_data()
    events = seasonal_data.get('events', [])
    if not events:
        return 0

    all_spots = db.get_all_attractions()
    count = 0

    for event in events:
        attraction_name = event.get('attraction_name', '')
        # 按名称匹配景点
        for spot in all_spots:
            spot_name = spot.get('name', '')
            if attraction_name in spot_name or spot_name in attraction_name:
                info = {
                    'attraction_id': spot['id'],
                    'season': event['season'],
                    'special_event': event.get('special_event', ''),
                    'crowd_prediction': event.get('crowd_prediction', ''),
                    'best_visit_time': event.get('best_visit_time', ''),
                    'tips': event.get('tips', ''),
                }
                try:
                    db.upsert_seasonal_info(info)
                    count += 1
                except Exception as e:
                    logger.warning(f"季节信息写入失败 [{attraction_name}]: {e}")
                break  # 只匹配第一个
        else:
            logger.debug(f"季节数据未匹配到景点: {attraction_name}")

    logger.info(f"季节信息补充完成: {count} 条")
    return count


def get_seasonal_general(season: str) -> dict:
    """
    获取某季节的通用旅游建议。

    Args:
        season: 春/夏/秋/冬
    Returns:
        季节通用数据字典
    """
    data = load_seasonal_data()
    return data.get('seasonal_general', {}).get(season, {})


def get_crowd_rules() -> dict:
    """获取人流预测规则"""
    data = load_seasonal_data()
    return data.get('crowd_rules', {})


# ============================================================
# 百度百科补充 (预留)
# ============================================================

def enrich_from_baike(name: str) -> Optional[Dict]:
    """
    从百度百科获取景点补充信息。

    当前为预留接口，返回None。可后续接入百度百科API或本地缓存。

    Args:
        name: 景点名称
    Returns:
        补充信息字典 或 None
    """
    # TODO: 接入百度百科API (需要合规授权)
    return None


# ============================================================
# 批量补充
# ============================================================

def run_enrichment(db: DBManager) -> Dict:
    """
    执行所有补充数据采集。

    Returns:
        {'seasonal': int, 'baike': int} 各类补充条数
    """
    result = {
        'seasonal': 0,
        'baike': 0,
    }

    # 季节性补充
    result['seasonal'] = enrich_seasonal_info(db)

    # 百度百科 (预留)
    # result['baike'] = ...

    return result
