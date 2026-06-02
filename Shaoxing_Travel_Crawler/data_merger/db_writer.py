"""
数据库写入器
================================
将ScraperHub采集的多源数据写入SQLite。
支持: 景点表、店铺表、活动表、路线表
"""

import logging
import json
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


def write_to_sqlite(data: Dict[str, List[Dict]], db_path: str = None) -> str:
    """
    将分类数据写入SQLite。

    Args:
        data: 分类后的数据 {category: [items]}
        db_path: 数据库路径
    Returns:
        数据库文件路径
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from data_layer.storage.db_manager import DBManager

    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent /
                      'data' / 'database' / 'shaoxing_travel.db')

    db = DBManager(Path(db_path))

    # 写入景点基础数据
    basic_items = data.get('attraction_basic', [])
    for item in basic_items:
        try:
            spot = {
                'name': item.get('名称', ''),
                'city': '绍兴',
                'address': item.get('地址', ''),
                'district': item.get('行政区', ''),
                'open_time': item.get('开放时间', ''),
                'ticket_price': item.get('门票价格', ''),
                'rating': float(item.get('评分', 0)) if item.get('评分') else 0,
                'summary': item.get('简介', ''),
                'source_url': item.get('来源URL', 'scraper_hub'),
                'source_platform': item.get('数据来源', 'multi_source'),
                'trust_level': item.get('信任等级', 1),
            }
            db.upsert_attraction(spot)
        except Exception as e:
            logger.debug(f"    写入失败 [{item.get('名称','?')}]: {e}")

    # 写入文化数据 (更新已有景点)
    culture_items = data.get('attraction_culture', [])
    for item in culture_items:
        try:
            name = item.get('名称', '')
            if name:
                existing = db.search_attractions(keyword=name, limit=1)
                if existing:
                    spot_id = existing[0]['id']
                    db.conn.execute(
                        "UPDATE attractions SET summary = summary || ? WHERE id = ?",
                        (f"\n[文化背景] {item.get('简介', '')}", spot_id)
                    )
                    db.conn.commit()
        except Exception as e:
            logger.debug(f"    文化数据更新失败 [{name}]: {e}")

    count = db.get_stats().get('total_spots', 0)
    db.close()
    logger.info(f"SQLite写入完成: {count} 景点")
    return str(db_path)
