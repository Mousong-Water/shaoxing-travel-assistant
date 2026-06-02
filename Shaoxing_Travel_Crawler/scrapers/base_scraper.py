"""
爬虫基类
================================
公共流程定义: 列表采集→详情采集→去重→保存CSV。
子类只需实现 fetch_list() 和 fetch_detail()，无需改动公共代码。

解决短板: #1 #4 #14 #15 (架构耦合、配置硬编码、空值不一致、缺少字段)
"""

import csv
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)


# ============================================================
# 标准化字段定义 (解决短板 #14 #15)
# ============================================================

# 所有爬虫统一输出的字段名
STD_FIELDNAMES = [
    '名称',       # name
    '城市',       # city
    '行政区',     # district
    '地址',       # address
    '开放时间',   # open_time
    '门票价格',   # ticket_price
    '游玩时长',   # duration_raw
    '评分',       # rating
    '评论数',     # review_count
    '标签',       # tags
    '分类',       # category
    '简介',       # summary
    '交通',       # transport_info
    '来源URL',    # source_url
    '来源平台',   # source_platform
]

# 空值统一处理: 确保所有字段至少有空字符串/0
STD_DEFAULTS = {
    '名称': '', '城市': '', '行政区': '', '地址': '',
    '开放时间': '', '门票价格': '', '游玩时长': '',
    '评分': 0, '评论数': 0, '标签': '', '分类': '',
    '简介': '', '交通': '', '来源URL': '', '来源平台': '',
}


def make_empty_spot(name: str = '', city: str = '',
                    url: str = '', platform: str = '') -> Dict:
    """创建空景点字典，所有字段统一初始值 (解决短板 #14)"""
    spot = dict(STD_DEFAULTS)
    spot['名称'] = name
    spot['城市'] = city
    spot['来源URL'] = url
    spot['来源平台'] = platform
    return spot


# ============================================================
# 爬虫基类
# ============================================================

class BaseScraper(ABC):
    """
    爬虫抽象基类。
    所有站点爬虫继承此类，只需实现两个方法即可接入公共流程。

    子类必须实现:
        fetch_list(page) → List[Dict]    # 列表页: 获取景点名称+URL
        fetch_detail(url, name) → Dict   # 详情页: 提取所有字段

    子类可选覆盖:
        _before_run()                    # 运行前钩子 (如获取Cookie)
        _save_csv(results)
    """

    def __init__(
        self,
        city_name: str = '绍兴',
        list_url: str = '',
        max_spots: int = 50,
        max_pages: int = 3,
        delay_min: float = 2.0,
        delay_max: float = 4.0,
        output_dir: Path = None,
        platform_name: str = '',
    ):
        """
        Args:
            city_name: 目标城市名
            list_url: 列表页起始URL
            max_spots: 最多爬取数量 (None=不限制)
            max_pages: 最多翻页数
            delay_min: 请求最小间隔(秒)
            delay_max: 请求最大间隔(秒)
            output_dir: CSV输出目录
            platform_name: 来源平台标识 (如 'ctrip')
        """
        self.city_name = city_name
        self.list_url = list_url
        self.max_spots = max_spots
        self.max_pages = max_pages
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.output_dir = output_dir or Path('.')
        self.platform_name = platform_name

    # ---- 子类必须实现 ----

    @abstractmethod
    def fetch_list(self, page: int = 1) -> List[Dict]:
        """
        爬取列表页。

        Args:
            page: 页码 (1-based)
        Returns:
            [{'name': str, 'url': str}, ...]
        """
        ...

    @abstractmethod
    def fetch_detail(self, url: str, name: str) -> Dict:
        """
        爬取详情页。

        Args:
            url: 详情页URL
            name: 景点名称 (备用)
        Returns:
            包含 STD_FIELDNAMES 字段的字典
        """
        ...

    # ---- 钩子 ----

    def _before_run(self):
        """运行前钩子: 初始化Cookie、Session等"""
        pass

    def _after_run(self, results: List[Dict]):
        """运行后钩子: 数据清洗、补充等"""
        pass

    # ---- 公共流程 ----

    def run(self, max_items: int = None) -> List[Dict]:
        """
        执行完整爬取流程 (模板方法)。

        流程:
            1. _before_run() - 初始化
            2. fetch_list(p1, p2, ...) - 收集景点链接
            3. fetch_detail(url, name) - 逐个爬详情
            4. _after_run() - 后处理
            5. _save_csv() - 保存结果

        Args:
            max_items: 覆盖max_spots配置
        Returns:
            爬取结果列表
        """
        max_items = max_items or self.max_spots
        logger.info(f"=== {self.platform_name} 爬虫开始 ({self.city_name}, 最多{max_items}个) ===")

        # Phase 0: 初始化
        self._before_run()

        # Phase 1: 列表页 → 收集链接
        all_links = self._collect_links(max_items)
        if not all_links:
            logger.warning("未收集到任何景点链接")
            return []

        # Phase 2: 详情页 → 提取数据
        results = self._scrape_details(all_links)

        # Phase 3: 后处理
        self._after_run(results)

        # Phase 4: 保存CSV
        if results:
            self._save_csv(results)

        logger.info(f"=== 爬取完成: {len(results)}/{len(all_links)} 个景点 ===")
        return results

    def _collect_links(self, max_items: int) -> List[Dict]:
        """收集所有列表页的景点链接 (含去重)"""
        all_links = []
        seen_urls = set()  # URL去重 (解决短板 #6)

        for page in range(1, self.max_pages + 1):
            if max_items and len(all_links) >= max_items:
                break

            try:
                links = self.fetch_list(page)
                if not links:
                    logger.info(f"第{page}页无更多结果，停止翻页")
                    break

                # 去重
                new_count = 0
                for link in links:
                    url = link.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_links.append(link)
                        new_count += 1

                logger.info(f"  第{page}页: {len(links)}个链接 → {new_count}个新链接")
            except Exception as e:
                logger.error(f"第{page}页采集失败: {e}")
                break

        # 截断
        all_links = all_links[:max_items] if max_items else all_links
        logger.info(f"共收集 {len(all_links)} 个唯一链接")
        return all_links

    def _scrape_details(self, links: List[Dict]) -> List[Dict]:
        """逐个爬取详情页"""
        import time, random
        results = []

        for i, link in enumerate(links):
            name = link.get('name', '?')
            url = link.get('url', '')
            logger.info(f"  [{i+1}/{len(links)}] {name}")

            # 频率控制 (解决短板 #7)
            if i > 0:
                delay = random.uniform(self.delay_min, self.delay_max)
                time.sleep(delay)

            try:
                detail = self.fetch_detail(url, name)
                results.append(detail)
            except Exception as e:
                logger.error(f"    ✗ 详情页失败 [{name}]: {e}")
                # 保存空记录，保持索引对齐
                from scrapers.base_scraper import make_empty_spot
                results.append(make_empty_spot(
                    name=name, city=self.city_name,
                    url=url, platform=self.platform_name,
                ))

        return results

    # ---- CSV输出 ----

    def _save_csv(self, results: List[Dict]) -> Path:
        """保存结果为UTF-8-SIG CSV"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = self.output_dir / f"{self.platform_name}_{self.city_name}_{timestamp}.csv"

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=STD_FIELDNAMES, extrasaction='ignore')
            writer.writeheader()
            for row in results:
                # 补齐缺失字段
                for field in STD_FIELDNAMES:
                    row.setdefault(field, STD_DEFAULTS.get(field, ''))
                writer.writerow(row)

        logger.info(f"CSV已保存: {csv_path} ({len(results)}条)")
        return csv_path
