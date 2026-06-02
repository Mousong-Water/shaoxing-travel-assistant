"""
数据清洗管线 v2.0
================================
解决问题: 2.1填空白字段 / 2.2统一分类 / 2.3去重合并
"""

import logging
from typing import Dict, List
from collections import defaultdict

logger = logging.getLogger(__name__)

# 统一5大分类
UNIFIED_CATEGORIES = {
    "景点": ["attraction_basic", "attraction_culture", "transport_info"],
    "美食店铺": ["food_shop", "local_food"],
    "文旅活动": ["seasonal_event", "official_notice"],
    "游玩攻略": ["attraction_review", "travel_route"],
    "非遗民俗": ["attraction_culture"],
}

CATEGORY_MAP = {}
for main_cat, sub_cats in UNIFIED_CATEGORIES.items():
    for sub in sub_cats:
        CATEGORY_MAP[sub] = main_cat


def fill_empty_fields(data: List[Dict]) -> List[Dict]:
    """填空白字段: 交通/人均/游玩时长/建议/贴士"""
    for item in data:
        defaults = {
            "交通": "暂无相关信息",
            "人均": "暂无相关信息",
            "游玩时长": "暂无相关信息",
            "游玩建议": "暂无相关信息",
            "贴士": "暂无相关信息",
            "地址": "暂无相关信息",
            "开放时间": "暂无相关信息",
            "门票价格": "暂无相关信息",
        }
        for field, default in defaults.items():
            if not item.get(field) or str(item.get(field, "")).strip() == "":
                item[field] = default
    return data


def unify_categories(data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """统一为5大分类"""
    unified = defaultdict(list)
    for cat, items in data.items():
        main_cat = CATEGORY_MAP.get(cat, "其他")
        for item in items:
            item["主分类"] = main_cat
            unified[main_cat].append(item)
    return dict(unified)


def dedup_by_name_source(data: List[Dict]) -> List[Dict]:
    """按名称+来源去重"""
    seen = set()
    result = []
    for item in data:
        name = item.get("名称") or item.get("店名") or item.get("标题") or item.get("景点") or item.get("线路名") or item.get("主题") or ""
        source = item.get("来源平台") or item.get("来源") or item.get("数据来源") or ""
        key = f"{name}|{source}"
        if key not in seen:
            seen.add(key)
            result.append(item)
    logger.info(f"去重: {len(result)}/{len(data)} 条")
    return result


def merge_spot_data(data: List[Dict]) -> List[Dict]:
    """合并同景点的多条数据为一条完整数据"""
    spots = defaultdict(dict)
    others = []

    for item in data:
        name = item.get("名称", "")
        if not name:
            others.append(item)
            continue

        if name not in spots:
            spots[name] = {"名称": name}

        # 合并非空字段
        for k, v in item.items():
            if k in ("名称", "_trust_level", "_data_category", "来源URL", "来源平台", "数据来源", "来源详情"):
                continue
            if v and str(v).strip() and str(v) != "暂无相关信息":
                existing = spots[name].get(k, "")
                if not existing or str(existing) == "暂无相关信息":
                    spots[name][k] = v

    merged = list(spots.values()) + others
    logger.info(f"合并: {len(data)} -> {len(merged)} 条")
    return merged


def remove_redundant_fields(data: List[Dict]) -> List[Dict]:
    """删除冗余字段"""
    redundant_patterns = ["_备选值", "_可信度", "quality_flags"]
    for item in data:
        keys_to_del = [k for k in item if any(p in k for p in redundant_patterns)]
        for k in keys_to_del:
            del item[k]
    return data


def clean_pipeline(data: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
    """完整清洗管线"""
    # 2.2: 统一分类
    unified = unify_categories(data)

    # 展开为列表
    all_items = []
    for cat, items in unified.items():
        all_items.extend(items)

    # 2.1: 填充空字段
    all_items = fill_empty_fields(all_items)

    # 2.3: 去重
    all_items = dedup_by_name_source(all_items)

    # 2.3: 合并同景点
    all_items = merge_spot_data(all_items)

    # 2.3: 删冗余字段
    all_items = remove_redundant_fields(all_items)

    # 重新分类
    result = defaultdict(list)
    for item in all_items:
        cat = item.get("主分类", "其他")
        result[cat].append(item)

    total = sum(len(v) for v in result.values())
    for cat, items in result.items():
        logger.info(f"  [{cat}]: {len(items)} 条")
    logger.info(f"清洗完成: {total} 条")
    return dict(result)
