"""
CSV导出器
================================
按分类导出多个CSV文件。
"""

import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# 各分类的CSV列定义
CATEGORY_COLUMNS = {
    'attraction_basic': ['名称', '行政区', '地址', '开放时间', '门票价格',
                         '评分', '简介', '信任等级', '数据来源', '冲突标记'],
    'attraction_culture': ['名称', '简介', '文化典故', '保护级别', '信任等级', '数据来源'],
    'attraction_review': ['景点', '游玩建议', '推荐游览顺序', '耗时', '贴士', '来源'],
    'food_shop': ['店名', '类型', '地址', '推荐', '人均', '简介', '来源'],
    'local_food': ['名称', '分类', '简介', '来源'],
    'seasonal_event': ['主题', '时间', '内容摘要', '来源'],
    'travel_route': ['线路名', '景点', '天数', '特色', '来源', '信任等级'],
    'official_notice': ['标题', '内容', '发布时间', '来源'],
    'transport_info': ['内容', '来源'],
}


def write_to_csv(data: Dict[str, List[Dict]], output_dir: Path = None) -> Dict[str, Path]:
    """
    按分类导出多个CSV文件。

    Args:
        data: 分类数据
        output_dir: 输出目录
    Returns:
        {category: csv_path}
    """
    if output_dir is None:
        output_dir = Path('Shaoxing_Travel_Crawler/output')
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    outputs = {}

    for cat, items in data.items():
        if not items:
            continue

        columns = CATEGORY_COLUMNS.get(cat, None)
        if columns is None:
            # 自动推断列
            columns = list(items[0].keys())
            # 过滤内部字段
            columns = [c for c in columns if not c.startswith('_')]

        csv_path = output_dir / f"{cat}_{timestamp}.csv"

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            for item in items:
                # 过滤掉内部字段
                clean_item = {k: v for k, v in item.items()
                              if not k.startswith('_') and k in columns}
                writer.writerow(clean_item)

        outputs[cat] = csv_path

    logger.info(f"CSV导出完成: {len(outputs)} 个文件 → {output_dir}")
    return outputs


def write_summary_csv(data: Dict[str, List[Dict]], output_path: Path = None) -> Path:
    """
    导出汇总CSV (所有分类合并到一个文件)。
    """
    if output_path is None:
        output_path = Path('Shaoxing_Travel_Crawler/output') / \
                      f"summary_{datetime.now():%Y%m%d_%H%M%S}.csv"

    all_items = []
    for cat, items in data.items():
        for item in items:
            item_copy = dict(item)
            item_copy['数据分类'] = cat
            all_items.append(item_copy)

    if not all_items:
        return output_path

    # 合并所有字段
    all_columns = set()
    for item in all_items:
        all_columns.update(k for k in item.keys() if not k.startswith('_'))
    columns = sorted(all_columns)

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        for item in all_items:
            clean = {k: v for k, v in item.items() if not k.startswith('_')}
            writer.writerow(clean)

    logger.info(f"汇总CSV: {output_path} ({len(all_items)}条)")
    return output_path
