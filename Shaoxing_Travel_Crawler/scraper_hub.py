"""
爬虫调用中心 ScraperHub
================================
统一管理所有数据源爬虫，支持:
  - 选择性爬取 (勾选数据源)
  - 并行调度 (多源同时采集)
  - 数据汇总 (按景点/主题自动归并)
  - 真实性验证 (多源交叉验证)
  - 分类筛选 (自动标签 + 质量过滤)

8大数据源:
  1. 绍兴公共数据开放平台 (data.sx.gov.cn)    ← 官方API, 100%合法
  2. 携程 (you.ctrip.com)                      ← 景点基础数据
  3. 百度百科 (baike.baidu.com)                ← 历史背景/文化典故
  4. 马蜂窝 (mafengwo.cn)                      ← 游记攻略/用户点评
  5. 大众点评 (dianping.com)                   ← 美食店铺/周边
  6. 搜狗微信 (weixin.sogou.com)               ← 文旅公众号文章
  7. 绍兴新闻网 (sxnews.cn)                     ← 本地活动/旅游动态
  8. 浙江省文旅厅 (ct.zj.gov.cn)               ← 非遗名录/精品线路

使用方式:
    hub = ScraperHub()
    hub.select_sources(['ctrip', 'gov_api', 'baike'])
    results = hub.run()
    verified = hub.verify(results)
    classified = hub.classify(verified)
    hub.export(classified, format='sqlite')
"""

import csv
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================
# 数据源定义
# ============================================================

class DataSource(Enum):
    """所有可用数据源"""
    GOV_API      = "gov_api"       # 绍兴公共数据开放平台
    CTRIP        = "ctrip"         # 携程
    BAIKE        = "baike"         # 百度百科
    MAFENGWO     = "mafengwo"      # 马蜂窝
    DIANPING     = "dianping"      # 大众点评
    WEIXIN       = "weixin"        # 搜狗微信
    LOCAL_NEWS   = "local_news"    # 绍兴本地新闻网
    WENGLV       = "wenglv"        # 浙江省文旅厅


@dataclass
class SourceInfo:
    """数据源元信息"""
    key: str
    name: str            # 中文名
    category: str        # 数据类别: 'attraction'/'food'/'activity'/'culture'/'general'
    requires_auth: bool  # 是否需要注册/API Key
    anti_crawl_level: str  # 反爬难度: 'none'/'low'/'medium'/'high'
    rate_limit: str      # 建议请求频率
    description: str
    enabled: bool = True


# 数据源注册表
SOURCE_REGISTRY: Dict[str, SourceInfo] = {
    "gov_api": SourceInfo(
        key="gov_api", name="绍兴公共数据开放平台",
        category="attraction",
        requires_auth=True,  # 需要注册app_id
        anti_crawl_level="none",  # 官方API!
        rate_limit="无限制 (官方接口)",
        description="政府开放数据: 景区服务人次、文化旅游数据，JSON API",
    ),
    "ctrip": SourceInfo(
        key="ctrip", name="携程",
        category="attraction",
        requires_auth=False,
        anti_crawl_level="high",  # 腾讯云WAF
        rate_limit="2-4秒/次",
        description="景点基本信息、评分、评论数、门票、开放时间",
    ),
    "baike": SourceInfo(
        key="baike", name="百度百科",
        category="culture",
        requires_auth=False,
        anti_crawl_level="low",
        rate_limit="1-2秒/次",
        description="景点历史背景、文化典故、建筑特色",
    ),
    "mafengwo": SourceInfo(
        key="mafengwo", name="马蜂窝",
        category="attraction",
        requires_auth=False,
        anti_crawl_level="medium",
        rate_limit="3-5秒/次",
        description="游记攻略、用户真实点评、游玩心得",
    ),
    "dianping": SourceInfo(
        key="dianping", name="大众点评",
        category="food",
        requires_auth=False,
        anti_crawl_level="medium",  # 静态搜索页可访问
        rate_limit="3-5秒/次",
        description="周边美食店铺、评分、人均消费、推荐菜",
    ),
    "weixin": SourceInfo(
        key="weixin", name="搜狗微信",
        category="activity",
        requires_auth=False,
        anti_crawl_level="low",
        rate_limit="2-3秒/次",
        description="文旅公众号文章: 时令推荐、新店开业、活动资讯",
    ),
    "local_news": SourceInfo(
        key="local_news", name="绍兴新闻网",
        category="activity",
        requires_auth=False,
        anti_crawl_level="low",
        rate_limit="1-2秒/次",
        description="本地新闻: 旅游动态、节庆活动、新景点开业",
    ),
    "wenglv": SourceInfo(
        key="wenglv", name="浙江省文旅厅",
        category="general",
        requires_auth=False,
        anti_crawl_level="none",  # 政府网站
        rate_limit="1秒/次",
        description="非遗名录、精品旅游线路、全省文旅资讯",
    ),
}


# ============================================================
# 数据内容分类
# ============================================================

class ContentType(Enum):
    """数据内容分类"""
    ATTRACTION_BASIC   = "attraction_basic"     # 景点基础信息
    ATTRACTION_CULTURE = "attraction_culture"   # 文化背景/典故
    ATTRACTION_REVIEW  = "attraction_review"    # 用户评价/游记
    FOOD_SHOP          = "food_shop"            # 美食店铺
    LOCAL_FOOD         = "local_food"           # 特色小吃/特产
    SEASONAL_EVENT     = "seasonal_event"       # 时令活动/节庆
    TRAVEL_ROUTE       = "travel_route"         # 推荐线路
    OFFICIAL_NOTICE    = "official_notice"      # 官方公告
    TRANSPORT_INFO     = "transport_info"       # 交通信息


# ============================================================
# ScraperHub 主类
# ============================================================

class ScraperHub:
    """
    爬虫调用中心。

    核心功能:
      1. 数据源选择与管理
      2. 并行/串行调度
      3. 多源数据汇总
      4. 真实性交叉验证
      5. 自动分类筛选
      6. 统一导出 (CSV/SQLite/JSON)
    """

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path("Shaoxing_Travel_Crawler/output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 已选择的数据源
        self._selected_sources: Set[str] = set()
        # 爬虫实例缓存
        self._scrapers: Dict[str, Any] = {}
        # 采集结果
        self._raw_results: Dict[str, List[Dict]] = {}
        # 验证结果
        self._verified_results: List[Dict] = []
        # 分类结果
        self._classified_results: Dict[str, List[Dict]] = {}

    # ============================================================
    # 数据源管理
    # ============================================================

    def list_sources(self) -> List[SourceInfo]:
        """列出所有可用数据源"""
        return list(SOURCE_REGISTRY.values())

    def list_sources_by_category(self, category: str) -> List[SourceInfo]:
        """按类别列出数据源 (attraction/food/activity/culture/general)"""
        return [s for s in SOURCE_REGISTRY.values()
                if s.category == category]

    def select_sources(self, source_keys: List[str]):
        """
        选择要爬取的数据源。

        Args:
            source_keys: 数据源key列表, 如 ['ctrip', 'gov_api', 'baike']
                        传 ['all'] 选择全部
        """
        if 'all' in source_keys:
            self._selected_sources = set(SOURCE_REGISTRY.keys())
        else:
            valid = set(SOURCE_REGISTRY.keys())
            invalid = set(source_keys) - valid
            if invalid:
                raise ValueError(f"未知数据源: {invalid}. 可用: {valid}")
            self._selected_sources = set(source_keys)

        logger.info(f"已选择数据源: {self._selected_sources}")

    def get_source_info(self, key: str) -> Optional[SourceInfo]:
        """获取数据源详情"""
        return SOURCE_REGISTRY.get(key)

    # ============================================================
    # 爬虫调度
    # ============================================================

    def run(
        self,
        sources: List[str] = None,
        parallel: bool = False,
        max_per_source: int = 30,
    ) -> Dict[str, List[Dict]]:
        """
        执行爬取任务。

        Args:
            sources: 数据源列表 (None=使用之前select的)
            parallel: 是否并行 (当前Python环境建议串行, 按需)
            max_per_source: 每个数据源最多采集条数
        Returns:
            {source_key: [data_dict, ...]}
        """
        if sources:
            self.select_sources(sources)

        if not self._selected_sources:
            raise ValueError("未选择任何数据源, 请先调用 select_sources()")

        self._raw_results = {}
        start_time = time.time()

        logger.info(f"=== ScraperHub 开始采集 {len(self._selected_sources)} 个数据源 ===")

        for source_key in self._selected_sources:
            info = SOURCE_REGISTRY[source_key]
            logger.info(f"\n--- [{source_key}] {info.name} ---")
            logger.info(f"  类别: {info.category} | 反爬: {info.anti_crawl_level} | 频率: {info.rate_limit}")

            try:
                scraper = self._get_scraper(source_key, max_per_source)
                if scraper is None:
                    logger.warning(f"  ✗ 跳过 (爬虫未实现或依赖缺失)")
                    continue

                results = scraper.run()
                self._raw_results[source_key] = results
                logger.info(f"  ✓ 采集完成: {len(results)} 条")
            except Exception as e:
                logger.error(f"  ✗ 采集失败: {e}", exc_info=True)
                self._raw_results[source_key] = []

        elapsed = time.time() - start_time
        total = sum(len(v) for v in self._raw_results.values())
        logger.info(f"\n=== ScraperHub 采集结束: {total}条 / {elapsed:.1f}秒 ===")

        return self._raw_results

    def _get_scraper(self, source_key: str, max_items: int):
        """懒加载爬虫实例"""
        if source_key in self._scrapers:
            return self._scrapers[source_key]

        scraper = None

        # 尝试导入对应的爬虫
        try:
            if source_key == 'ctrip':
                from scrapers.ctrip_scraper import CtripScraper
                scraper = CtripScraper(
                    render_mode='auto',
                    max_spots=max_items,
                    playwright_headless=True,
                )
            elif source_key == 'gov_api':
                from scrapers.gov_api_scraper import GovApiScraper
                scraper = GovApiScraper(max_items=max_items)
            elif source_key == 'baike':
                from scrapers.baike_scraper import BaikeScraper
                scraper = BaikeScraper(max_items=max_items)
            elif source_key == 'mafengwo':
                from scrapers.mafengwo_scraper import MafengwoScraper
                scraper = MafengwoScraper(max_items=max_items)
            elif source_key == 'dianping':
                from scrapers.dianping_scraper import DianpingScraper
                scraper = DianpingScraper(max_items=max_items)
            elif source_key == 'weixin':
                from scrapers.weixin_search import WeixinSearchScraper
                scraper = WeixinSearchScraper(max_items=max_items)
            elif source_key == 'local_news':
                from scrapers.local_news_scraper import LocalNewsScraper
                scraper = LocalNewsScraper(max_items=max_items)
            elif source_key == 'wenglv':
                from scrapers.wenglv_scraper import WenglvScraper
                scraper = WenglvScraper(max_items=max_items)
        except ImportError as e:
            logger.warning(f"    爬虫 [{source_key}] 导入失败: {e}")
            return None
        except Exception as e:
            logger.error(f"    爬虫 [{source_key}] 初始化失败: {e}")
            return None

        self._scrapers[source_key] = scraper
        return scraper

    # ============================================================
    # 数据真实性验证 (Phase C)
    # ============================================================

    def verify(self, results: Dict[str, List[Dict]] = None) -> List[Dict]:
        """
        多源交叉验证: 同一信息在多个数据源中出现则可信度更高。

        验证规则:
          1. 单源数据 → trust_level=1 (仅参考)
          2. 双源一致 → trust_level=2 (较可信)
          3. 三源及以上 → trust_level=3 (高可信)
          4. 与官方数据一致 → trust_level=4 (权威)
          5. 矛盾数据 → flag冲突, 标记为需人工核实
        """
        if results is None:
            results = self._raw_results

        from data_verifier.cross_validator import CrossValidator
        validator = CrossValidator()
        self._verified_results = validator.validate(results)
        return self._verified_results

    # ============================================================
    # 数据分类筛选 (Phase D)
    # ============================================================

    def classify(self, verified_data: List[Dict] = None) -> Dict[str, List[Dict]]:
        """
        自动分类: 按内容类型归类。

        Returns:
            {
                'attraction_basic': [...],
                'attraction_culture': [...],
                'food_shop': [...],
                'seasonal_event': [...],
                'travel_route': [...],
                ...
            }
        """
        if verified_data is None:
            verified_data = self._verified_results

        from data_classifier.content_classifier import ContentClassifier
        classifier = ContentClassifier()
        self._classified_results = classifier.classify(verified_data)
        return self._classified_results

    # ============================================================
    # 数据导出
    # ============================================================

    def export(
        self,
        data: Any = None,
        format: str = 'sqlite',
        output_path: str = None,
    ):
        """
        统一导出。

        Args:
            data: 要导出的数据 (默认使用分类后的数据)
            format: 'sqlite' / 'csv' / 'json'
            output_path: 输出路径
        """
        if data is None:
            data = self._classified_results or self._verified_results or self._raw_results

        if format == 'sqlite':
            from data_merger.db_writer import write_to_sqlite
            path = write_to_sqlite(data, output_path)
            logger.info(f"已导出SQLite: {path}")
        elif format == 'csv':
            from data_merger.csv_writer import write_to_csv
            path = write_to_csv(data, output_path or self.output_dir)
            logger.info(f"已导出CSV: {path}")
        elif format == 'json':
            import json
            path = output_path or str(self.output_dir / f"hub_export_{datetime.now():%Y%m%d_%H%M%S}.json")
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"已导出JSON: {path}")

    # ============================================================
    # 状态查询
    # ============================================================

    def status(self) -> Dict:
        """获取当前状态"""
        return {
            'selected_sources': list(self._selected_sources),
            'raw_counts': {k: len(v) for k, v in self._raw_results.items()},
            'verified_count': len(self._verified_results),
            'classified_categories': list(self._classified_results.keys()),
            'total_items': sum(len(v) for v in self._classified_results.values()),
        }

    def summary(self) -> str:
        """生成可读摘要"""
        s = self.status()
        lines = [
            "=" * 50,
            "  ScraperHub 状态",
            "=" * 50,
            f"  已选数据源: {s['selected_sources']}",
            f"  原始数据: {s['raw_counts']}",
            f"  验证后: {s['verified_count']} 条",
            f"  分类: {s['classified_categories']}",
            f"  总计: {s['total_items']} 条",
            "=" * 50,
        ]
        return '\n'.join(lines)


# ============================================================
# 便捷入口
# ============================================================

def quick_collect(
    sources: List[str] = None,
    max_per_source: int = 20,
    auto_verify: bool = True,
    auto_classify: bool = True,
) -> ScraperHub:
    """
    快速采集入口。

    使用:
        hub = quick_collect(['ctrip', 'baike', 'gov_api'])
        print(hub.summary())
        hub.export(format='sqlite')
    """
    hub = ScraperHub()

    if sources is None:
        sources = ['ctrip', 'baike', 'gov_api']  # 默认三源

    hub.select_sources(sources)
    hub.run(max_per_source=max_per_source)

    if auto_verify:
        hub.verify()
    if auto_classify:
        hub.classify()

    return hub
