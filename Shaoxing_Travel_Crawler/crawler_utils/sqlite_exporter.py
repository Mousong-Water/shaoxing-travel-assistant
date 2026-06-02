"""
CSV → SQLite 一键入库工具
================================
将爬虫导出的CSV规范化后写入SQLite数据库。
解决短板: #20 (无SQLite出口)

使用:
    from crawler_utils.sqlite_exporter import export_to_sqlite
    export_to_sqlite('shaoxing_scraper_output.csv')
"""

import csv
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 轻量数据规范化 (在爬虫侧完成，避免依赖data_layer)
# ============================================================

def normalize_duration(raw: str) -> Optional[int]:
    """游玩时长 → 分钟数"""
    if not raw:
        return None

    # "1-3小时" → 120
    m = re.search(r'(\d+\.?\d*)\s*[-~至到]\s*(\d+\.?\d*)\s*(?:小时|h)', raw)
    if m:
        return int((float(m.group(1)) + float(m.group(2))) / 2 * 60)

    # "半天" → 240
    if any(w in raw for w in ['半天', '半日']):
        return 240

    # "2小时" → 120
    m = re.search(r'(\d+\.?\d*)\s*(?:小时|h)', raw)
    if m:
        return int(float(m.group(1)) * 60)

    # "90分钟" → 90
    m = re.search(r'(\d+)\s*分钟', raw)
    if m:
        return int(m.group(1))

    return None


def normalize_ticket(raw: str) -> tuple:
    """门票 → (文本, 数值)"""
    if not raw:
        return ('', None)
    if any(w in raw for w in ['免费', '不收费', '免票']):
        return ('免费', 0.0)
    nums = re.findall(r'[\d.]+', raw)
    if nums:
        n = float(nums[0])
        return (f'{int(n)}元' if n == int(n) else f'{n}元', n)
    return (raw.strip(), None)


def normalize_rating(raw) -> float:
    """评分 → 0-5 float"""
    try:
        r = float(raw)
        if r > 50:
            return r / 20.0
        if r <= 1.0:
            return r * 5.0
        return r
    except (ValueError, TypeError):
        return 0.0


# ============================================================
# CSV → SQLite 一键入库
# ============================================================

def export_to_sqlite(
    csv_path: str,
    db_path: str = None,
    drop_existing: bool = False,
) -> int:
    """
    将爬虫CSV导入SQLite数据库。

    自动完成: 字段映射 → 数据规范化 → 去重入库

    Args:
        csv_path: 爬虫输出的CSV文件路径
        db_path: SQLite数据库路径 (默认: data/database/shaoxing_travel.db)
        drop_existing: 是否清空已有数据
    Returns:
        入库条数
    """
    # 延迟导入，避免爬虫层依赖data_layer
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from data_layer.storage.db_manager import DBManager
    from data_layer.quality.data_cleaner import infer_category, compute_popularity_score

    if db_path is None:
        db_path = str(Path(__file__).parent.parent.parent / 'data' / 'database' / 'shaoxing_travel.db')

    csv_path = Path(csv_path)
    if not csv_path.exists():
        logger.error(f"CSV不存在: {csv_path}")
        return 0

    db = DBManager(Path(db_path))

    if drop_existing:
        db.conn.execute("DELETE FROM attractions")
        db.conn.commit()
        logger.info("已清空旧数据")

    # 读取CSV并转换
    spots = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 字段映射: CSV中文列 → DB英文列
            dur_min = normalize_duration(row.get('游玩时长', ''))

            spot = {
                'name': row.get('名称', ''),
                'city': row.get('城市', '绍兴'),
                'address': row.get('地址', ''),
                'district': row.get('行政区', ''),
                'open_time': row.get('开放时间', ''),
                'ticket_price': normalize_ticket(row.get('门票价格', ''))[0],
                'ticket_numeric': normalize_ticket(row.get('门票价格', ''))[1],
                'duration_min': dur_min,
                'rating': normalize_rating(row.get('评分', 0)),
                'review_count': int(row.get('评论数', 0)) if row.get('评论数') else 0,
                'tags': row.get('标签', ''),
                'category': infer_category(
                    row.get('名称', ''),
                    row.get('标签', ''),
                    row.get('简介', ''),
                ),
                'summary': row.get('简介', ''),
                'transport_info': row.get('交通', ''),
                'source_url': row.get('来源URL', f"csv_import:{row.get('名称', '')}"),
                'source_platform': row.get('来源平台', 'ctrip'),
                'popularity_score': 0,
                'data_quality': 0.7,
            }

            # 热度分
            spot['popularity_score'] = compute_popularity_score(
                spot['rating'],
                spot['review_count'],
            )

            spots.append(spot)

    # 批量入库
    count = db.upsert_attractions_batch(spots)
    db.close()

    logger.info(f"一键入库完成: {count}/{len(spots)} 条 → {db_path}")
    return count


# ============================================================
# BaseScraper扩展: to_sqlite方法
# ============================================================

def scraper_to_sqlite(scraper_results: List[Dict], csv_path: str = None,
                      db_path: str = None) -> int:
    """
    将爬虫结果直接写入SQLite (先存CSV再入库)。

    Args:
        scraper_results: 爬虫.run()的返回结果
        csv_path: CSV临时路径 (默认crawler目录下)
        db_path: 数据库路径
    Returns:
        入库条数
    """
    import csv
    from scrapers.base_scraper import STD_FIELDNAMES

    if csv_path is None:
        from datetime import datetime
        csv_path = Path(__file__).parent.parent / f"scraper_export_{datetime.now():%Y%m%d_%H%M%S}.csv"

    # 保存临时CSV
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=STD_FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        for row in scraper_results:
            writer.writerow(row)

    # 入库
    return export_to_sqlite(str(csv_path), db_path=db_path)
