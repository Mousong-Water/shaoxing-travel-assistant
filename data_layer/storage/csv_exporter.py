"""
CSV导入导出工具
================================
景点数据与CSV文件互转，兼容旧版爬虫输出格式。
"""
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from shared.config import ScraperConfig, RAW_DATA_DIR
from shared.logging_config import logger
from data_layer.storage.db_manager import DBManager


# CSV字段映射: CSV列名 → 数据库列名
CSV_TO_DB_MAP = {
    '名称': 'name',
    '城市': 'city',
    '地址': 'address',
    '开放时间': 'open_time',
    '门票价格': 'ticket_price',
    '游玩时长': 'duration_raw',    # 临时字段，cleaner解析后生成 duration_min
    '评分': 'rating',
    '标签': 'tags',
    '简介': 'summary',
    '交通': 'transport_info',
}

# 数据库列 → CSV列 (逆映射)
DB_TO_CSV_MAP = {v: k for k, v in CSV_TO_DB_MAP.items()}

# CSV输出列顺序
CSV_FIELDNAMES = [
    '名称', '城市', '行政区', '地址', '开放时间', '门票价格',
    '游玩时长', '评分', '评论数', '标签', '分类', '简介',
    '交通', '适宜季节', '热度分数', '拥挤程度', '数据质量',
    '来源URL', '更新时间',
]


def import_csv_to_db(csv_path: Path, db: DBManager) -> int:
    """
    将爬虫生成的CSV导入SQLite。

    Args:
        csv_path: CSV文件路径
        db: DBManager实例
    Returns:
        导入的景点数量
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error(f"CSV文件不存在: {csv_path}")
        return 0

    spots = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            spot = {}
            for csv_col, db_col in CSV_TO_DB_MAP.items():
                value = row.get(csv_col, '')
                spot[db_col] = value

            # 数值转换
            try:
                spot['rating'] = float(spot['rating']) if spot.get('rating') else 0
            except (ValueError, TypeError):
                spot['rating'] = 0

            # 时长解析: duration_raw → duration_min
            from data_layer.quality.data_cleaner import parse_duration
            dur_text, dur_min = parse_duration(spot.get('duration_raw', ''))
            spot['duration_min'] = dur_min

            # 门票解析: ticket_price → ticket_numeric
            from data_layer.quality.data_cleaner import parse_ticket_price
            price_text, price_num = parse_ticket_price(spot.get('ticket_price', ''))
            spot['ticket_price'] = price_text or spot.get('ticket_price', '')
            spot['ticket_numeric'] = price_num

            # 必填字段
            spot['city'] = spot.get('city', '绍兴')
            spot['source_platform'] = 'ctrip'
            spot['source_url'] = f"csv_import:{spot.get('name', 'unknown')}"

            # 默认值
            spot.setdefault('data_quality', 0.5)
            spot.setdefault('popularity_score', 0)

            spots.append(spot)

    count = db.upsert_attractions_batch(spots)
    logger.info(f"CSV导入完成: {csv_path.name} → {count} 条")
    return count


def export_db_to_csv(db: DBManager, output_path: Path = None) -> Path:
    """
    将SQLite中的所有景点导出为CSV。

    Args:
        db: DBManager实例
        output_path: 输出路径 (默认: data/raw/ 带时间戳)
    Returns:
        CSV文件路径
    """
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = RAW_DATA_DIR / f"shaoxing_export_{timestamp}.csv"

    spots = db.get_all_attractions()

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
        writer.writeheader()

        for spot in spots:
            row = {
                '名称': spot.get('name', ''),
                '城市': spot.get('city', '绍兴'),
                '行政区': spot.get('district', ''),
                '地址': spot.get('address', ''),
                '开放时间': spot.get('open_time', ''),
                '门票价格': spot.get('ticket_price', ''),
                '游玩时长': f"{spot.get('duration_min', '')}分钟" if spot.get('duration_min') else '',
                '评分': spot.get('rating', ''),
                '评论数': spot.get('review_count', ''),
                '标签': spot.get('tags', ''),
                '分类': spot.get('category', ''),
                '简介': spot.get('summary', ''),
                '交通': spot.get('transport_info', ''),
                '适宜季节': spot.get('season_suitable', ''),
                '热度分数': spot.get('popularity_score', ''),
                '拥挤程度': spot.get('crowd_level', ''),
                '数据质量': f"{spot.get('data_quality', 0):.0%}",
                '来源URL': spot.get('source_url', ''),
                '更新时间': spot.get('last_updated', ''),
            }
            writer.writerow(row)

    logger.info(f"CSV导出完成: {len(spots)} 条 → {output_path}")
    return output_path


def read_csv_preview(csv_path: Path, max_rows: int = 5) -> List[Dict]:
    """
    读取CSV文件前N行预览。

    Args:
        csv_path: CSV文件路径
        max_rows: 最大行数
    Returns:
        景点字典列表
    """
    if not csv_path.exists():
        return []

    rows = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)
    return rows
