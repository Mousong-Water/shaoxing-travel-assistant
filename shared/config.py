"""
全局配置
================================
所有硬编码参数集中管理，支持环境变量覆盖。
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装，跳过

# ============================================================
# 项目路径
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DATABASE_DIR = DATA_DIR / "database"
VECTOR_DIR = DATA_DIR / "vectors"
PROFILE_DIR = DATA_DIR / "profiles"

# 确保目录存在
for d in [RAW_DATA_DIR, DATABASE_DIR, VECTOR_DIR, PROFILE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================
# 爬虫配置
# ============================================================
class ScraperConfig:
    """携程爬虫参数"""
    # 目标城市 (URL中的城市标识)
    CITY_SLUG = "shaoxing18"
    CITY_NAME = "绍兴"
    LIST_URL = f"https://you.ctrip.com/sight/{CITY_SLUG}/s0-p1.html"
    LIST_URL_TEMPLATE = f"https://you.ctrip.com/sight/{CITY_SLUG}/s0-p{{page}}.html"

    # 请求控制
    MAX_PAGES = 3            # 最大翻页数 (每页约10个景点)
    MAX_SPOTS = 50           # 最多爬取景点数 (None=不限制)
    DELAY_MIN = 2.0          # 请求最小间隔(秒)
    DELAY_MAX = 4.0          # 请求最大间隔(秒)
    REQUEST_TIMEOUT = 30     # 请求超时(秒)
    MAX_RETRIES = 3          # 最大重试次数
    RETRY_BACKOFF = 2.0      # 重试退避倍数

    # Playwright配置
    PLAYWRIGHT_HEADLESS = False  # 有头模式绕过WAF
    PLAYWRIGHT_WAIT = 5          # 页面加载等待(秒)
    PLAYWRIGHT_TIMEOUT = 60000   # 页面超时(毫秒)

    # 输出文件
    CSV_OUTPUT_TEMPLATE = "shaoxing_attractions_{timestamp}.csv"

    # User-Agent池
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]


# ============================================================
# 数据库配置
# ============================================================
class DatabaseConfig:
    """SQLite数据库参数"""
    DB_PATH = DATABASE_DIR / "shaoxing_travel.db"
    CSV_IMPORT_BATCH_SIZE = 50


# ============================================================
# RAG配置
# ============================================================
class RAGConfig:
    """检索增强生成参数"""
    EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
    CHROMA_COLLECTION = "shaoxing_spots"
    CHROMA_PERSIST_DIR = str(VECTOR_DIR)
    TOP_K_RETRIEVAL = 15          # RAG检索返回数
    SEMANTIC_WEIGHT = 0.7         # 语义搜索权重
    KEYWORD_WEIGHT = 0.3          # 关键词搜索权重


# ============================================================
# 路线规划配置
# ============================================================
class PlanningConfig:
    """路线规划参数"""
    # 评分权重 (总和=1.0)
    SCORE_INTEREST_WEIGHT = 0.40      # 兴趣匹配
    SCORE_RATING_WEIGHT = 0.20        # 评分
    SCORE_POPULARITY_WEIGHT = 0.15    # 热度
    SCORE_SEASONAL_WEIGHT = 0.15      # 季节匹配
    SCORE_BUDGET_WEIGHT = 0.10        # 预算匹配

    # 时间约束
    MEAL_BREAK_LUNCH_MIN = 60       # 午餐时间(分钟)
    MEAL_BREAK_SNACK_MIN = 30       # 小憩时间(分钟)
    WITHIN_DISTRICT_TRANSIT_MIN = 20  # 同区交通(分钟)
    CROSS_DISTRICT_TRANSIT_MIN = 45   # 跨区交通(分钟)
    FAMILY_PACE_FACTOR = 0.8          # 家庭模式减速因子
    COMPACT_PACE_FACTOR = 1.2         # 紧凑模式加速因子

    # 日照时间 (按月份, 小时)
    DAYLIGHT_HOURS = {
        1: 10, 2: 10.5, 3: 11.5, 4: 12.5,
        5: 13.5, 6: 14, 7: 14, 8: 13.5,
        9: 12.5, 10: 11.5, 11: 10.5, 12: 10,
    }

    # 路线生成
    NUM_ALTERNATIVES = 4           # 生成路线方案数
    MAX_SPOTS_PER_DAY = 4          # 每天最多景点数
    MIN_SPOTS_PER_DAY = 1          # 每天最少景点数


# ============================================================
# 调度器配置
# ============================================================
class SchedulerConfig:
    """定时更新参数"""
    UPDATE_INTERVAL_HOURS = 6      # 爬取间隔(小时)
    ENABLE_SCHEDULER = True        # 是否启用定时器


# ============================================================
# 模型API配置
# ============================================================
class ModelConfig:
    """多模型API密钥和参数 (从环境变量读取)"""
    # Claude
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL = "claude-sonnet-4-20250514"

    # OpenAI / GPT
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    GPT_MODEL = "gpt-4o-mini"

    # 本地模型 (Ollama)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    LOCAL_MODEL = "qwen2.5:7b"

    # 模型路由策略
    ROUTING = {
        "preference_extraction": "local",     # 偏好提取 → 本地模型
        "route_planning": "claude",           # 路线规划 → Claude/GPT
        "route_commentary": "claude",         # 路线解说 → Claude
        "spot_summary": "gpt",                # 景点摘要 → GPT-4o-mini
        "rag_query": "local",                 # RAG问答 → 本地模型
    }

    # 请求控制
    MAX_TOKENS_DEFAULT = 2048
    TEMPERATURE_DEFAULT = 0.7


# ============================================================
# 全局配置单例
# ============================================================
class Config:
    scraper = ScraperConfig()
    database = DatabaseConfig()
    rag = RAGConfig()
    planning = PlanningConfig()
    scheduler = SchedulerConfig()
    models = ModelConfig()

    # 调试模式
    DEBUG = os.getenv("TRAVEL_DEBUG", "false").lower() == "true"
    DEMO_MODE = os.getenv("TRAVEL_DEMO_MODE", "false").lower() == "true"
