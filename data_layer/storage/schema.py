"""
数据库Schema定义与迁移管理
================================
定义SQLite表结构和索引，支持版本化迁移。
"""

import sqlite3
from pathlib import Path
from shared.config import DatabaseConfig
from shared.logging_config import logger

CURRENT_SCHEMA_VERSION = 1


class Schema:
    """SQLite Schema管理器 - 建表 + 迁移 + 索引"""

    # ============================================================
    # 表定义 SQL
    # ============================================================

    TABLE_ATTRACTIONS = """
    CREATE TABLE IF NOT EXISTS attractions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT    NOT NULL,                  -- 景点名称
        city            TEXT    NOT NULL DEFAULT '绍兴',    -- 所属城市
        address         TEXT,                              -- 地址
        district        TEXT,                              -- 行政区 (越城区/柯桥区/上虞区等)
        lat             REAL,                              -- 纬度
        lng             REAL,                              -- 经度
        open_time       TEXT,                              -- 开放时间
        ticket_price    TEXT,                              -- 门票价格 (文本, 如"80元")
        ticket_numeric  REAL,                              -- 数值门票 (用于排序/评分)
        duration_min    INTEGER,                           -- 建议游玩时长(分钟)
        rating          REAL,                              -- 评分 (0-5)
        review_count    INTEGER DEFAULT 0,                 -- 评论数
        tags            TEXT,                              -- 标签 (|分隔)
        category        TEXT,                              -- 分类 (自然风光/人文历史/主题公园等)
        summary         TEXT,                              -- 简介
        transport_info  TEXT,                              -- 交通信息
        season_suitable TEXT,                              -- 适宜季节 (春|夏|秋|冬)
        popularity_score REAL DEFAULT 0,                   -- 综合热度分数
        crowd_level     TEXT,                              -- 拥挤程度 (低/中/高)
        source_url      TEXT UNIQUE,                       -- 数据来源URL (去重键)
        source_platform TEXT DEFAULT 'ctrip',              -- 来源平台
        data_quality    REAL DEFAULT 0,                    -- 数据完整度评分 (0-1)
        last_updated    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    TABLE_SEASONAL_INFO = """
    CREATE TABLE IF NOT EXISTS seasonal_info (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        attraction_id   INTEGER NOT NULL,
        season          TEXT NOT NULL,                     -- 春/夏/秋/冬
        special_event   TEXT,                              -- 季节性活动
        crowd_prediction TEXT,                             -- 该季节拥挤预测
        best_visit_time TEXT,                              -- 最佳游览时段
        tips            TEXT,                              -- 季节游览提示
        FOREIGN KEY (attraction_id) REFERENCES attractions(id) ON DELETE CASCADE,
        UNIQUE(attraction_id, season)
    );
    """

    TABLE_USER_PROFILES = """
    CREATE TABLE IF NOT EXISTS user_profiles (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_name        TEXT,
        travel_days         INTEGER DEFAULT 1,
        budget_level        TEXT DEFAULT '中等',            -- 经济/中等/高端
        pace_preference     TEXT DEFAULT '适中',            -- 轻松/适中/紧凑
        interests           TEXT,                          -- 兴趣标签 (|分隔)
        accessibility_needs INTEGER DEFAULT 0,
        family_with_kids    INTEGER DEFAULT 0,
        prefer_morning      INTEGER DEFAULT 1,
        travel_month        INTEGER DEFAULT 1,
        dietary_notes       TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    TABLE_SAVED_ROUTES = """
    CREATE TABLE IF NOT EXISTS saved_routes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id      INTEGER,
        route_name      TEXT,
        personality     TEXT,                              -- 路线个性 (均衡/深度/热门/小众)
        days            INTEGER,
        spots_json      TEXT,                              -- JSON: [{spot_id, order, duration_min}]
        total_score     REAL,
        commentary      TEXT,                              -- LLM生成的整体解说
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (profile_id) REFERENCES user_profiles(id) ON DELETE SET NULL
    );
    """

    TABLE_SCRAPER_RUNS = """
    CREATE TABLE IF NOT EXISTS scraper_runs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        finished_at     TIMESTAMP,
        status          TEXT DEFAULT 'running',            -- running/success/failed
        spots_scraped   INTEGER DEFAULT 0,
        spots_new       INTEGER DEFAULT 0,
        spots_updated   INTEGER DEFAULT 0,
        error_message   TEXT,
        duration_sec    REAL
    );
    """

    # 索引
    INDEXES = [
        "CREATE INDEX IF NOT EXISTS idx_att_name        ON attractions(name);",
        "CREATE INDEX IF NOT EXISTS idx_att_district    ON attractions(district);",
        "CREATE INDEX IF NOT EXISTS idx_att_rating      ON attractions(rating);",
        "CREATE INDEX IF NOT EXISTS idx_att_popularity  ON attractions(popularity_score);",
        "CREATE INDEX IF NOT EXISTS idx_att_duration    ON attractions(duration_min);",
        "CREATE INDEX IF NOT EXISTS idx_att_category    ON attractions(category);",
        "CREATE INDEX IF NOT EXISTS idx_att_quality     ON attractions(data_quality);",
        "CREATE INDEX IF NOT EXISTS idx_season_att      ON seasonal_info(attraction_id);",
        "CREATE INDEX IF NOT EXISTS idx_season_season   ON seasonal_info(season);",
    ]

    # Schema版本表
    TABLE_VERSION = """
    CREATE TABLE IF NOT EXISTS schema_version (
        version     INTEGER PRIMARY KEY,
        applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT
    );
    """

    @classmethod
    def initialize(cls, db_path: Path = None) -> sqlite3.Connection:
        """
        初始化数据库: 建表 + 建索引 + 版本记录。

        Args:
            db_path: 数据库文件路径 (默认从config读取)
        Returns:
            sqlite3.Connection (已开启WAL模式和外键约束)
        """
        if db_path is None:
            db_path = DatabaseConfig.DB_PATH

        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))

        # 性能优化设置
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")

        # 建表
        for ddl in [
            cls.TABLE_ATTRACTIONS,
            cls.TABLE_SEASONAL_INFO,
            cls.TABLE_USER_PROFILES,
            cls.TABLE_SAVED_ROUTES,
            cls.TABLE_SCRAPER_RUNS,
            cls.TABLE_VERSION,
        ]:
            conn.execute(ddl)

        # 建索引
        for idx_sql in cls.INDEXES:
            conn.execute(idx_sql)

        # 记录版本
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, description) VALUES (?, ?)",
            (CURRENT_SCHEMA_VERSION, "Initial schema")
        )

        conn.commit()
        logger.info(f"数据库初始化完成: {db_path} (v{CURRENT_SCHEMA_VERSION})")
        return conn

    @classmethod
    def get_version(cls, conn: sqlite3.Connection) -> int:
        """获取当前schema版本"""
        try:
            cur = conn.execute("SELECT MAX(version) FROM schema_version;")
            row = cur.fetchone()
            return row[0] if row[0] else 0
        except sqlite3.OperationalError:
            return 0
