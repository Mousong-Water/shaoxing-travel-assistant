"""
实体合并引擎 (旅游行业标准)
================================
将多源数据按规则合并为"实体"（景点/店铺/展馆），
攻略/笔记/活动等"内容"独立存储并关联实体ID。

合并规则:
  1. 名称相似度 > 0.6 视为候选
  2. 地理位置距离 < 500m 视为同一实体
  3. 分类一致 (景点/美食店铺/非遗民俗)

字段优先级:
  官方网站 > 马蜂窝 > 大众点评 > 携程 > 小红书 > 百度百科

输出:
  entities: 合并后的实体表 (~500-1000条)
  contents: 关联的内容表 (~3000-5000条)
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from difflib import SequenceMatcher
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 来源优先级 (数字越小优先级越高)
SOURCE_PRIORITY = {
    "gov_api": 1, "government": 1, "wenglv": 1, "official": 1,
    "ctrip": 2, "mafengwo": 3, "mafengwo_static": 3,
    "dianping": 3, "dianping_static": 3,
    "xiaohongshu": 4, "xiaohongshu_static": 4,
    "baike": 5, "baike_static": 5, "encyclopedia_static": 5,
    "weixin": 6, "weixin_search": 6, "weixin_static": 6,
    "zhihu": 6, "zhihu_static": 6,
    "local_news": 7, "sxnews_static": 7,
    "comprehensive": 3,
    "unknown": 99,
}

# 实体类型定义
ENTITY_TYPES = {
    "景点": ["attraction_basic", "attraction_culture", "transport_info"],
    "美食店铺": ["food_shop", "local_food"],
    "非遗民俗": ["attraction_culture"],
    "展馆": ["attraction_basic"],
}

# 内容类型定义 (不合并，独立存储)
CONTENT_TYPES = [
    "attraction_review", "travel_route", "seasonal_event",
    "official_notice", "local_food",
]


@dataclass
class Entity:
    """合并后的实体"""
    entity_id: str = ""
    name: str = ""
    entity_type: str = ""  # 景点/美食店铺/非遗民俗/展馆
    category: str = ""     # 子分类
    address: str = ""
    district: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None
    open_time: str = ""
    ticket_price: str = ""
    ticket_numeric: Optional[float] = None
    duration_min: Optional[int] = None
    rating: float = 0.0
    rating_weight: float = 0.0  # 用于加权平均
    review_count: int = 0
    tags: str = ""
    summary: str = ""
    transport: str = ""
    image_urls: str = ""
    heritage_level: str = ""
    best_season: str = ""
    popularity_score: float = 0.0
    data_quality: float = 0.0
    trust_level: int = 1
    sources: List[str] = field(default_factory=list)
    source_count: int = 0
    # 内容关联
    content_ids: List[str] = field(default_factory=list)


class EntityMerger:
    """实体合并引擎"""

    def __init__(self, name_threshold: float = 0.75, geo_threshold_m: float = 500):
        self.name_threshold = name_threshold
        self.geo_threshold = geo_threshold_m
        # 必须三重校验都满足才合并
        self.require_geo = True       # 必须地理相近
        self.require_category = True  # 必须同分类

    def merge(self, all_data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        主入口: 分离实体和内容，合并实体，关联内容。

        Returns:
            (entities_list, contents_list)
            每个都是可导出为CSV的字典列表
        """
        # Step 1: 分离实体数据和内容数据
        entity_candidates, content_items = self._split_entity_content(all_data)
        logger.info(f"分离: 实体候选{len(entity_candidates)}条, 内容{len(content_items)}条")

        # Step 2: 实体合并
        merged_entities = self._merge_entities(entity_candidates)
        logger.info(f"合并: {len(entity_candidates)}条候选 → {len(merged_entities)}个实体")

        # Step 3: 内容关联实体
        contents_linked = self._link_contents(content_items, merged_entities)
        linked = sum(1 for c in contents_linked if c.get('entity_id'))
        logger.info(f"关联: {len(contents_linked)}条内容, {linked}条关联到实体")

        # Step 4: 转为字典输出
        entity_dicts = [self._entity_to_dict(e) for e in merged_entities]
        return entity_dicts, contents_linked

    def _split_entity_content(self, all_data: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """分离实体候选和内容条目"""
        entities = []
        contents = []

        for item in all_data:
            cat = item.get("_data_category", "") or item.get("内容分类", "") or item.get("主分类", "")
            name = (item.get("名称") or item.get("店名") or
                    item.get("景点") or item.get("线路名") or
                    item.get("标题") or item.get("主题") or "")

            if not name:
                continue

            # 内容判定规则 (满足任一即为内容):
            is_content = False

            # 规则1: 数据类别明确为内容型
            content_cats = ["attraction_review", "travel_route", "seasonal_event",
                          "official_notice", "local_food", "游玩攻略", "文旅活动"]
            for cc in content_cats:
                if cc in cat:
                    is_content = True
                    break

            # 规则2: 字段特征为内容型
            if (item.get("游玩建议") or item.get("推荐游览顺序") or
                item.get("路线") or item.get("推荐路线") or
                item.get("内容摘要") or item.get("时间") or
                item.get("贴士")):
                # 但排除有完整地址的实体数据
                if not (item.get("地址") and item.get("开放时间")):
                    is_content = True

            # 规则3: 线路和活动
            if (item.get("线路名") or item.get("主题") or item.get("标题")):
                if not (item.get("地址") and len(item.get("地址", "")) > 5):
                    is_content = True

            # 规则4: 菜品信息属于内容
            if item.get("所属店铺") or (item.get("分类") and item.get("分类") in ["土特产","糕点","甜品"]):
                is_content = True

            # Assign
            if is_content:
                item["_entity_type"] = "content"
                contents.append(item)
            else:
                item["_entity_type"] = self._classify_entity(item)
                entities.append(item)

        return entities, contents

    def _classify_entity(self, item: Dict) -> str:
        """归类实体类型"""
        cat = item.get("_data_category", "") or item.get("主分类", "") or ""
        name = item.get("名称", "") or item.get("店名", "")

        if "food" in cat or "美食" in cat or "店铺" in str(item.get("分类", "")):
            return "美食店铺"
        if "非遗" in cat or "民俗" in cat or "heritage" in str(item.get("文化类型", "")):
            return "非遗民俗"
        if "博物馆" in name or "展馆" in name or "科技馆" in name or "美术馆" in name or "图书馆" in name or "剧院" in name:
            return "展馆"
        if "category" in cat.lower():
            return "展馆"
        return "景点"

    def _merge_entities(self, candidates: List[Dict]) -> List[Entity]:
        """核心合并算法"""
        # Group by entity type first
        by_type = defaultdict(list)
        for c in candidates:
            by_type[c.get("_entity_type", "景点")].append(c)

        all_entities = []
        entity_counter = [0]

        for etype, items in by_type.items():
            # Within each type, cluster by name similarity + geo
            clusters = self._cluster_by_name_geo(items)
            for cluster in clusters:
                entity = self._merge_cluster(cluster, etype, entity_counter)
                all_entities.append(entity)

        return all_entities

    def _cluster_by_name_geo(self, items: List[Dict]) -> List[List[Dict]]:
        """按名称相似度+地理位置聚类"""
        if len(items) <= 1:
            return [items] if items else []

        # Simple greedy clustering
        clusters = []
        used = set()

        for i, item in enumerate(items):
            if i in used:
                continue

            cluster = [item]
            used.add(i)
            name_i = item.get("名称", "") or item.get("店名", "")
            lat_i = item.get("lat") or item.get("纬度")
            lng_i = item.get("lng") or item.get("经度")

            for j, other in enumerate(items):
                if j in used:
                    continue
                name_j = other.get("名称", "") or other.get("店名", "")
                lat_j = other.get("lat") or other.get("纬度")
                lng_j = other.get("lng") or other.get("经度")

                # 三重校验: 名称 + 地理 + 分类
                name_sim = self._name_similarity(name_i, name_j)

                # Geo distance
                geo_close = True
                if lat_i and lng_i and lat_j and lng_j:
                    try:
                        dist = self._geo_distance(
                            float(lat_i), float(lng_i),
                            float(lat_j), float(lng_j)
                        )
                        geo_close = dist < self.geo_threshold
                    except (ValueError, TypeError):
                        geo_close = not self.require_geo  # 无坐标时宽松

                # Category match
                cat_i = item.get("_entity_type", "") or item.get("分类", "")
                cat_j = other.get("_entity_type", "") or other.get("分类", "")
                cat_match = (cat_i == cat_j) if self.require_category else True
                if not cat_i or not cat_j:
                    cat_match = not self.require_category

                # All three must pass
                if name_sim > self.name_threshold and geo_close and cat_match:
                    cluster.append(other)
                    used.add(j)

            clusters.append(cluster)

        return clusters

    def _name_similarity(self, a: str, b: str) -> float:
        """计算名称相似度 (0-1)"""
        if not a or not b:
            return 0
        # Clean
        a = re.sub(r'[（(][^)）]*[)）]', '', a).strip()
        b = re.sub(r'[（(][^)）]*[)）]', '', b).strip()
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.9
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _geo_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Haversine距离 (米)"""
        from math import radians, cos, sin, asin, sqrt
        R = 6371000
        dlat = radians(lat2 - lat1)
        dlng = radians(lng2 - lng1)
        a_val = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
        return R * 2 * asin(sqrt(a_val))

    def _merge_cluster(self, cluster: List[Dict], etype: str,
                       counter: List[int]) -> Entity:
        """合并一个聚类中的所有候选为单个实体"""
        counter[0] += 1
        entity = Entity(
            entity_id=f"{etype[:2].upper()}{counter[0]:04d}",
            entity_type=etype,
        )

        # Sort by source priority
        sorted_items = sorted(
            cluster,
            key=lambda x: SOURCE_PRIORITY.get(
                x.get("来源平台", "") or x.get("来源", "") or x.get("数据来源", "") or "unknown", 99
            )
        )

        # Merge fields with priority
        entity.name = self._best_field(sorted_items, ["名称", "店名"])
        entity.address = self._best_field(sorted_items, ["地址"], priority=True)
        entity.district = self._best_field(sorted_items, ["行政区"])
        entity.open_time = self._best_field(sorted_items, ["开放时间"], priority=True)
        entity.ticket_price = self._best_field(sorted_items, ["门票价格"], priority=True)

        # Ticket numeric
        for item in sorted_items:
            if item.get("ticket_numeric") is not None:
                entity.ticket_numeric = item["ticket_numeric"]
                break

        entity.duration_min = self._best_numeric(sorted_items, ["duration_min", "游玩时长"])

        # Rating: weighted average
        ratings = []
        for item in sorted_items:
            r = item.get("评分") or item.get("rating")
            if r:
                try:
                    w = 6 - SOURCE_PRIORITY.get(
                        item.get("来源平台", "unknown"), 99
                    )
                    ratings.append((float(r), max(w, 1)))
                except (ValueError, TypeError):
                    pass
        if ratings:
            total_w = sum(w for _, w in ratings)
            entity.rating = sum(r * w for r, w in ratings) / total_w if total_w > 0 else 0
            entity.rating_weight = total_w

        # Summary: longest
        summaries = [(item.get("简介", "") or item.get("summary", ""), len(item.get("简介", "") or ""))
                     for item in sorted_items]
        entity.summary = max(summaries, key=lambda x: x[1])[0] if summaries else ""

        # Tags: collect all unique
        all_tags = set()
        for item in sorted_items:
            tags = item.get("标签", "") or item.get("tags", "")
            for t in str(tags).replace("|", ",").split(","):
                t = t.strip()
                if t and len(t) > 1:
                    all_tags.add(t)
        entity.tags = "|".join(sorted(all_tags))

        # Transport: best non-default
        entity.transport = self._best_field(sorted_items, ["交通", "transport_info"],
                                            skip_default=True)

        # Image URLs: collect from all
        all_imgs = []
        for item in sorted_items:
            imgs = item.get("图片URL", "") or item.get("image_urls", "")
            if isinstance(imgs, list):
                all_imgs.extend(imgs)
            elif isinstance(imgs, str) and imgs:
                all_imgs.extend([u.strip() for u in imgs.split("|") if u.strip()])
        entity.image_urls = "|".join(dict.fromkeys(all_imgs))  # dedup preserve order

        # Geo
        for item in sorted_items:
            lat = item.get("lat") or item.get("纬度")
            lng = item.get("lng") or item.get("经度")
            if lat and lng:
                try:
                    entity.lat = float(lat)
                    entity.lng = float(lng)
                    break
                except (ValueError, TypeError):
                    pass

        # Other
        entity.heritage_level = self._best_field(sorted_items, ["保护级别", "heritage_level", "_heritage_level"])
        entity.best_season = self._best_field(sorted_items, ["适宜季节", "best_season", "最佳季节"])
        entity.category = self._best_field(sorted_items, ["分类", "category", "_entity_type"])
        entity.review_count = self._best_numeric(sorted_items, ["评论数", "review_count"]) or 0
        entity.popularity_score = self._best_numeric(sorted_items, ["popularity_score", "热度分数"]) or 0
        entity.data_quality = self._best_numeric(sorted_items, ["data_quality", "数据质量"]) or 0.5

        # Trust & sources
        entity.trust_level = max(item.get("信任等级", item.get("_trust_level", 1))
                                 for item in sorted_items)
        entity.sources = list(dict.fromkeys(
            item.get("来源平台", "") or item.get("来源", "") or item.get("数据来源", "")
            for item in sorted_items if item.get("来源平台") or item.get("来源")
        ))
        entity.source_count = len(cluster)

        return entity

    def _best_field(self, items: List[Dict], keys: List[str],
                    priority: bool = True, skip_default: bool = False) -> str:
        """从候选中取最佳字段值"""
        for item in items:
            for key in keys:
                val = item.get(key, "")
                if val and str(val).strip():
                    if skip_default and "暂无相关信息" in str(val):
                        continue
                    return str(val).strip()
        # Fallback to any non-empty
        for item in items:
            for key in keys:
                val = item.get(key, "")
                if val and str(val).strip():
                    return str(val).strip()
        return ""

    def _best_numeric(self, items: List[Dict], keys: List[str]) -> Optional[float]:
        """从候选中取最佳数值"""
        for item in items:
            for key in keys:
                val = item.get(key)
                if val is not None and val != "":
                    # Try to parse duration text
                    if isinstance(val, str) and "小时" in val:
                        from data_layer.quality.data_cleaner import parse_duration
                        _, mins = parse_duration(val)
                        if mins:
                            return mins
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        continue
        return None

    def _link_contents(self, contents: List[Dict],
                       entities: List[Entity]) -> List[Dict]:
        """将内容条目关联到最匹配的实体"""
        for content in contents:
            content_name = (content.get("景点") or content.get("名称") or
                           content.get("标题") or content.get("主题") or "")
            if not content_name:
                content["entity_id"] = ""
                continue

            # Find best matching entity
            best_entity = None
            best_score = 0
            for entity in entities:
                score = self._name_similarity(content_name, entity.name)
                # Also check if entity name appears in content title
                if entity.name in content_name:
                    score = max(score, 0.85)
                if content_name in entity.name:
                    score = max(score, 0.85)

                if score > best_score:
                    best_score = score
                    best_entity = entity

            if best_entity and best_score > 0.5:
                content["entity_id"] = best_entity.entity_id
                content["entity_name"] = best_entity.name
                best_entity.content_ids.append(content.get("来源URL", ""))
            else:
                content["entity_id"] = ""
                content["entity_name"] = ""

        return contents

    def _entity_to_dict(self, entity: Entity) -> Dict:
        """Entity → 可导出字典"""
        return {
            "entity_id": entity.entity_id,
            "名称": entity.name,
            "实体类型": entity.entity_type,
            "分类": entity.category,
            "地址": entity.address,
            "行政区": entity.district,
            "纬度": entity.lat,
            "经度": entity.lng,
            "开放时间": entity.open_time,
            "门票价格": entity.ticket_price,
            "门票数值": entity.ticket_numeric,
            "游玩时长(分钟)": entity.duration_min,
            "评分": round(entity.rating, 1) if entity.rating else 0,
            "评论数": entity.review_count,
            "标签": entity.tags,
            "简介": entity.summary[:500] if entity.summary else "",
            "交通": entity.transport,
            "图片URL": entity.image_urls,
            "保护级别": entity.heritage_level,
            "适宜季节": entity.best_season,
            "热度分数": entity.popularity_score,
            "数据质量": entity.data_quality,
            "信任等级": entity.trust_level,
            "来源列表": "|".join(entity.sources),
            "来源数量": entity.source_count,
            "关联内容数": len(entity.content_ids),
        }
