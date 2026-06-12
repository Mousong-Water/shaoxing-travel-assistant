"""
爬虫轻量基类 ScraperMixin
==========================
解决4个假爬虫共性问题:
  1. URL去重 (非标题去重)
  2. 可配置阈值 (非硬编码)
  3. 字段统一 (实时+回退一致)
  4. 标准run()模式: 实时优先→回退补充

使用:
  class MyScraper(ScraperMixin):
      def __init__(self, **kwargs):
          super().__init__(**kwargs)
          self.rm = RequestManager(...)

      def _scrape_live(self) -> List[Dict]:
          ...  # 真实HTTP

      def _fallback_data(self) -> List[Dict]:
          ...  # 静态回退
"""

import logging
from typing import List, Dict, Set, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ScraperMixin(ABC):
    """爬虫轻量基类 — 统一URL去重、阈值配置、字段规范"""

    def __init__(
        self,
        max_items: int = 50,              # 总产出上限
        max_per_query: int = 8,           # 每个搜索词最多取几条
        min_live_threshold: int = 5,      # 实时不足N条时触发回退
        max_live_total: int = 40,         # 实时采集全局上限
        query_list: List[str] = None,     # 可配置搜索词
    ):
        self.max_items = max_items
        self.max_per_query = max_per_query
        self.min_live_threshold = min_live_threshold
        self.max_live_total = max_live_total
        self.query_list = query_list or []

        # URL去重集合
        self._seen_urls: Set[str] = set()

    # ---- 子类必须实现 ----

    @abstractmethod
    def _scrape_live(self) -> List[Dict]:
        """真实HTTP采集 (子类实现)"""
        ...

    @abstractmethod
    def _fallback_data(self) -> List[Dict]:
        """静态回退数据 (子类实现)"""
        ...

    @abstractmethod
    def _platform_name(self) -> str:
        """返回来源平台标识 (如 'zhihu', 'dianping')"""
        ...

    # ---- 公共流程 ----

    def run(self) -> List[Dict]:
        """标准采集流程: 实时优先 → 不足阈值 → 回退补充"""
        results = []

        # 1. 实时
        live = self._scrape_live()
        results.extend(live)
        logger.info(f"[{self._platform_name()}] 实时: {len(live)} 条")

        # 2. 回退
        if len(results) < self.min_live_threshold:
            fb = self._fallback_data()
            for item in fb:
                item["来源平台"] = f"{self._platform_name()}_fallback"
                item["_trust_level"] = 1
            results.extend(fb)
            logger.info(f"[{self._platform_name()}] 回退: {len(fb)} 条")

        return results[:self.max_items]

    # ---- 去重 ----

    def is_duplicate(self, url: str) -> bool:
        """URL去重 (解决标题去重不准问题)"""
        if not url:
            return False
        if url in self._seen_urls:
            return True
        self._seen_urls.add(url)
        return False

    # ---- 标准字段构建 ----

    def make_item(self, overrides: dict = None) -> Dict:
        """创建统一字段的条目 (解决字段不一致问题)"""
        item = {
            "标题": "",
            "摘要": "",
            "链接": "",
            "搜索词": "",
            "点赞": 0,
            "来源平台": self._platform_name(),
            "来源URL": "",
            "_data_category": "attraction_review",
            "_trust_level": 2,
        }
        if overrides:
            item.update(overrides)
        return item

    @staticmethod
    def parse_likes(like_text: str) -> int:
        """解析点赞数: '3.2w'→32000, '1200'→1200"""
        if not like_text:
            return 0
        try:
            t = str(like_text).lower().strip().replace(',', '').replace('，', '')
            if 'w' in t or '万' in t:
                return int(float(t.replace('w', '').replace('万', '').strip()) * 10000)
            if 'k' in t or '千' in t:
                return int(float(t.replace('k', '').replace('千', '').strip()) * 1000)
            return int(float(t))
        except (ValueError, TypeError):
            return 0
