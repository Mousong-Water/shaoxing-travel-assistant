"""
数据库操作管理器
================================
提供景点、季节信息、用户画像、路线的CRUD操作。
所有数据库操作集中在此，便于维护和测试。
"""
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from contextlib import contextmanager

from shared.config import DatabaseConfig
from shared.logging_config import logger
from data_layer.storage.schema import Schema


class DBManager:
    """SQLite数据库管理器 - CRUD操作封装"""

    def __init__(self, db_path: Path = None):
        """
        初始化数据库连接。

        Args:
            db_path: 数据库文件路径 (默认从config读取)
        """
        self.db_path = db_path or DatabaseConfig.DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    # ---- 连接管理 ----

    def _row_to_dict(self, row) -> Dict:
        """将sqlite3.Row转换为dict"""
        if row is None:
            return None
        return {k: row[k] for k in row.keys()}

    @property
    def conn(self) -> sqlite3.Connection:
        """懒加载获取连接，自动初始化schema"""
        if self._conn is None:
            self._conn = Schema.initialize(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    @contextmanager
    def transaction(self):
        """事务上下文管理器 - 自动commit或rollback"""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ============================================================
    # 景点 CRUD
    # ============================================================

    def upsert_attraction(self, spot: Dict[str, Any]) -> int:
        """
        插入或更新景点数据 (按source_url去重)。

        Args:
            spot: 景点数据字典，字段名与数据库列名一致
        Returns:
            景点的id
        """
        columns = [
            'name', 'city', 'address', 'district', 'lat', 'lng',
            'open_time', 'ticket_price', 'ticket_numeric', 'duration_min',
            'rating', 'review_count', 'tags', 'category', 'summary',
            'transport_info', 'season_suitable', 'popularity_score',
            'crowd_level', 'source_url', 'source_platform', 'data_quality',
        ]

        # 只保留有效列
        values = {k: spot.get(k, '') for k in columns}
        values['last_updated'] = datetime.now().isoformat()

        # 构建 INSERT ... ON CONFLICT UPDATE
        placeholders = ', '.join([f':{c}' for c in columns])
        updates = ', '.join([
            f"{c}=excluded.{c}" for c in columns
        ] + ['last_updated=excluded.last_updated'])

        sql = f"""
            INSERT INTO attractions ({', '.join(columns)}, last_updated)
            VALUES ({placeholders}, :last_updated)
            ON CONFLICT(source_url) DO UPDATE SET {updates}
        """

        with self.transaction() as conn:
            cur = conn.execute(sql, values)
            # 获取id (新插入或已存在的)
            cur = conn.execute(
                "SELECT id FROM attractions WHERE source_url = ?",
                (spot.get('source_url', ''),)
            )
            row = cur.fetchone()
            return row[0] if row else -1

    def upsert_attractions_batch(self, spots: List[Dict[str, Any]]) -> int:
        """批量插入/更新景点，返回新增数量"""
        count = 0
        for spot in spots:
            try:
                spot_id = self.upsert_attraction(spot)
                if spot_id > 0:
                    count += 1
            except Exception as e:
                logger.warning(f"Upsert失败 [{spot.get('name', '?')}]: {e}")
        logger.info(f"批量upsert完成: {count}/{len(spots)} 条")
        return count

    def get_attraction(self, spot_id: int) -> Optional[Dict]:
        """根据ID获取景点"""
        cur = self.conn.execute(
            "SELECT * FROM attractions WHERE id = ?", (spot_id,)
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def get_attraction_by_url(self, url: str) -> Optional[Dict]:
        """根据source_url获取景点"""
        cur = self.conn.execute(
            "SELECT * FROM attractions WHERE source_url = ?", (url,)
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def search_attractions(
        self,
        keyword: str = None,
        district: str = None,
        category: str = None,
        min_rating: float = None,
        max_price: float = None,
        season: str = None,
        min_quality: float = 0.3,
        order_by: str = "popularity_score DESC",
        limit: int = 50,
    ) -> List[Dict]:
        """
        多条件景点搜索。

        Args:
            keyword: 名称/简介关键词
            district: 行政区筛选
            category: 分类筛选
            min_rating: 最低评分
            max_price: 最高门票价格
            season: 适宜季节
            min_quality: 最低数据质量
            order_by: 排序方式
            limit: 返回数量上限
        Returns:
            景点字典列表
        """
        conditions = ["data_quality >= :min_quality"]
        params = {"min_quality": min_quality, "limit": limit}

        if keyword:
            conditions.append("(name LIKE :kw OR summary LIKE :kw OR tags LIKE :kw)")
            params["kw"] = f"%{keyword}%"

        if district:
            conditions.append("district = :district")
            params["district"] = district

        if category:
            conditions.append("category = :category")
            params["category"] = category

        if min_rating is not None:
            conditions.append("rating >= :min_rating")
            params["min_rating"] = min_rating

        if max_price is not None:
            conditions.append("(ticket_numeric <= :max_price OR ticket_numeric IS NULL)")
            params["max_price"] = max_price

        if season:
            conditions.append("season_suitable LIKE :season")
            params["season"] = f"%{season}%"

        where = " AND ".join(conditions)
        sql = f"SELECT * FROM attractions WHERE {where} ORDER BY {order_by} LIMIT :limit"

        cur = self.conn.execute(sql, params)
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_all_attractions(self, limit: int = None) -> List[Dict]:
        """获取所有景点"""
        sql = "SELECT * FROM attractions ORDER BY popularity_score DESC"
        if limit:
            sql += f" LIMIT {limit}"
        cur = self.conn.execute(sql)
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_districts(self) -> List[str]:
        """获取所有行政区列表"""
        cur = self.conn.execute(
            "SELECT DISTINCT district FROM attractions WHERE district != '' ORDER BY district"
        )
        return [r[0] for r in cur.fetchall()]

    def get_categories(self) -> List[str]:
        """获取所有分类列表"""
        cur = self.conn.execute(
            "SELECT DISTINCT category FROM attractions WHERE category != '' ORDER BY category"
        )
        return [r[0] for r in cur.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {}
        cur = self.conn.execute("SELECT COUNT(*) FROM attractions")
        stats['total_spots'] = cur.fetchone()[0]

        cur = self.conn.execute(
            "SELECT COUNT(*) FROM attractions WHERE data_quality >= 0.6"
        )
        stats['high_quality_spots'] = cur.fetchone()[0]

        cur = self.conn.execute("SELECT AVG(rating) FROM attractions WHERE rating > 0")
        stats['avg_rating'] = round(cur.fetchone()[0] or 0, 2)

        # 最后更新时间
        cur = self.conn.execute(
            "SELECT MAX(last_updated) FROM attractions"
        )
        stats['last_update'] = cur.fetchone()[0] or "从未更新"

        # 分类分布
        cur = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM attractions WHERE category != '' "
            "GROUP BY category ORDER BY cnt DESC"
        )
        stats['category_distribution'] = dict(cur.fetchall())

        return stats

    # ============================================================
    # 季节信息 CRUD
    # ============================================================

    def upsert_seasonal_info(self, info: Dict[str, Any]) -> int:
        """插入或更新季节信息"""
        columns = ['attraction_id', 'season', 'special_event',
                    'crowd_prediction', 'best_visit_time', 'tips']
        values = {k: info.get(k, '') for k in columns}
        placeholders = ', '.join([f':{c}' for c in columns])
        updates = ', '.join([f"{c}=excluded.{c}" for c in columns])

        sql = f"""
            INSERT INTO seasonal_info ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT(attraction_id, season) DO UPDATE SET {updates}
        """

        with self.transaction() as conn:
            conn.execute(sql, values)
            cur = conn.execute("SELECT last_insert_rowid()")
            return cur.fetchone()[0]

    def get_seasonal_info(self, attraction_id: int, season: str = None) -> List[Dict]:
        """获取景点的季节信息"""
        if season:
            cur = self.conn.execute(
                "SELECT * FROM seasonal_info WHERE attraction_id = ? AND season = ?",
                (attraction_id, season)
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM seasonal_info WHERE attraction_id = ?",
                (attraction_id,)
            )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    # ============================================================
    # 用户画像 CRUD
    # ============================================================

    def save_profile(self, profile: Dict[str, Any]) -> int:
        """保存用户画像"""
        columns = [
            'profile_name', 'travel_days', 'budget_level', 'pace_preference',
            'interests', 'accessibility_needs', 'family_with_kids',
            'prefer_morning', 'travel_month', 'dietary_notes',
        ]
        values = {k: profile.get(k, '') for k in columns}

        if 'id' in profile and profile['id']:
            # 更新已有画像
            set_clause = ', '.join([f"{c}=:{c}" for c in columns])
            sql = f"UPDATE user_profiles SET {set_clause} WHERE id=:id"
            values['id'] = profile['id']
            with self.transaction() as conn:
                conn.execute(sql, values)
            return profile['id']
        else:
            # 新建画像
            placeholders = ', '.join([f':{c}' for c in columns])
            sql = f"INSERT INTO user_profiles ({', '.join(columns)}) VALUES ({placeholders})"
            with self.transaction() as conn:
                conn.execute(sql, values)
                cur = conn.execute("SELECT last_insert_rowid()")
                return cur.fetchone()[0]

    def get_profiles(self) -> List[Dict]:
        """获取所有用户画像"""
        cur = self.conn.execute(
            "SELECT * FROM user_profiles ORDER BY created_at DESC"
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]

    def get_profile(self, profile_id: int) -> Optional[Dict]:
        """获取单个画像"""
        cur = self.conn.execute(
            "SELECT * FROM user_profiles WHERE id = ?", (profile_id,)
        )
        row = cur.fetchone()
        return self._row_to_dict(row) if row else None

    def delete_profile(self, profile_id: int) -> bool:
        """删除用户画像"""
        with self.transaction() as conn:
            conn.execute("DELETE FROM user_profiles WHERE id = ?", (profile_id,))
        return True

    # ============================================================
    # 路线 CRUD
    # ============================================================

    def save_route(self, route: Dict[str, Any]) -> int:
        """保存路线"""
        columns = [
            'profile_id', 'route_name', 'personality', 'days',
            'spots_json', 'total_score', 'commentary',
        ]
        values = {k: route.get(k, '') for k in columns}
        # 序列化spots列表
        if isinstance(values.get('spots_json'), (list, dict)):
            values['spots_json'] = json.dumps(values['spots_json'], ensure_ascii=False)

        placeholders = ', '.join([f':{c}' for c in columns])
        sql = f"INSERT INTO saved_routes ({', '.join(columns)}) VALUES ({placeholders})"

        with self.transaction() as conn:
            conn.execute(sql, values)
            cur = conn.execute("SELECT last_insert_rowid()")
            return cur.fetchone()[0]

    def get_routes(self, profile_id: int = None) -> List[Dict]:
        """获取历史路线"""
        if profile_id:
            cur = self.conn.execute(
                "SELECT * FROM saved_routes WHERE profile_id = ? ORDER BY created_at DESC",
                (profile_id,)
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM saved_routes ORDER BY created_at DESC"
            )

        routes = []
        for row in cur.fetchall():
            route = self._row_to_dict(row)
            if route.get('spots_json') and isinstance(route['spots_json'], str):
                route['spots_json'] = json.loads(route['spots_json'])
            routes.append(route)
        return routes

    # ============================================================
    # 爬虫运行日志
    # ============================================================

    def start_scraper_run(self) -> int:
        """记录爬虫运行开始，返回run_id"""
        with self.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO scraper_runs (status, spots_scraped) VALUES ('running', 0)"
            )
            return cur.lastrowid

    def finish_scraper_run(self, run_id: int, spots_scraped: int,
                           spots_new: int, spots_updated: int,
                           error: str = None):
        """记录爬虫运行结束"""
        status = 'failed' if error else 'success'
        sql = """
            UPDATE scraper_runs
            SET finished_at = ?, status = ?, spots_scraped = ?,
                spots_new = ?, spots_updated = ?, error_message = ?,
                duration_sec = (julianday(finished_at) - julianday(started_at)) * 86400
            WHERE id = ?
        """
        self.conn.execute(sql, (
            datetime.now().isoformat(), status, spots_scraped,
            spots_new, spots_updated, error, run_id
        ))
        self.conn.commit()

    def get_scraper_runs(self, limit: int = 10) -> List[Dict]:
        """获取最近的爬虫运行记录"""
        cur = self.conn.execute(
            "SELECT * FROM scraper_runs ORDER BY started_at DESC LIMIT ?",
            (limit,)
        )
        return [self._row_to_dict(row) for row in cur.fetchall()]


# ============================================================
# 工厂函数
# ============================================================

def create_db_manager(db_path: Path = None) -> DBManager:
    """创建DBManager实例并初始化数据库"""
    if db_path is None:
        db_path = DatabaseConfig.DB_PATH
    return DBManager(db_path)
