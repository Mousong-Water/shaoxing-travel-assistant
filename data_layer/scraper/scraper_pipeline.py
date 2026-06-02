"""
爬虫管线
================================
编排爬虫→清洗→验证→入库的完整流程。
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from shared.config import Config, RAW_DATA_DIR
from data_layer.scraper.ctrip_scraper import CtripScraper
from data_layer.quality.data_cleaner import clean_batch
from data_layer.quality.quality_validator import validate_batch, filter_low_quality
from data_layer.storage.db_manager import DBManager
from data_layer.storage.csv_exporter import export_db_to_csv

logger = logging.getLogger(__name__)


class ScraperPipeline:
    """
    爬虫管线: 采集 → 清洗 → 验证 → 入库 → CSV备份

    使用示例:
        pipeline = ScraperPipeline()
        spots = pipeline.run_full(max_items=30)
    """

    def __init__(self, db: DBManager = None):
        """
        Args:
            db: DBManager实例 (默认自动创建)
        """
        self.db = db or DBManager()
        self.scraper = CtripScraper(Config.scraper)

    def run_full(
        self,
        max_items: int = None,
        skip_scrape: bool = False,
        csv_path: Path = None,
    ) -> List[Dict]:
        """
        执行完整数据管线。

        Args:
            max_items: 最大爬取数量
            skip_scrape: 跳过爬取，直接从CSV导入 (调试用)
            csv_path: 要导入的CSV路径 (配合skip_scrape)
        Returns:
            入库后的景点数据列表
        """
        run_id = self.db.start_scraper_run()
        spots_raw = []
        spots_new = 0
        spots_updated = 0
        error = None

        try:
            # Step 1: 采集
            if skip_scrape and csv_path:
                logger.info(f"跳过爬取，从CSV导入: {csv_path}")
                from data_layer.storage.csv_exporter import import_csv_to_db
                import_csv_to_db(csv_path, self.db)
                spots_raw = []
            else:
                logger.info(f"[Step 1/4] 爬取景点数据 (最多{max_items or '不限'}个)...")
                spots_raw = self.scraper.run(max_items=max_items)

            if not spots_raw:
                if skip_scrape:
                    logger.info("管线完成 (仅CSV导入)")
                    self.db.finish_scraper_run(run_id, 0, 0, 0)
                    return []
                logger.warning("未爬取到任何景点数据")

            # Step 2: 清洗
            logger.info(f"[Step 2/4] 数据清洗 ({len(spots_raw)}条)...")
            spots_clean = clean_batch(spots_raw)

            # Step 3: 验证
            logger.info(f"[Step 3/4] 质量验证...")
            spots_validated = validate_batch(spots_clean)

            # Step 4: 入库
            logger.info(f"[Step 4/4] 写入数据库...")
            for spot in spots_validated:
                try:
                    existing = self.db.get_attraction_by_url(spot.get('source_url', ''))
                    if existing:
                        # 只更新数据质量更高的记录
                        if spot.get('data_quality', 0) >= existing.get('data_quality', 0):
                            self.db.upsert_attraction(spot)
                            spots_updated += 1
                    else:
                        self.db.upsert_attraction(spot)
                        spots_new += 1
                except Exception as e:
                    logger.warning(f"入库失败 [{spot.get('name', '?')}]: {e}")

            # CSV备份
            export_db_to_csv(self.db)

            logger.info(f"管线完成: 新增{spots_new}, 更新{spots_updated}")

        except Exception as e:
            error = str(e)
            logger.error(f"管线执行失败: {e}", exc_info=True)
            raise
        finally:
            self.db.finish_scraper_run(
                run_id,
                spots_scraped=len(spots_raw),
                spots_new=spots_new,
                spots_updated=spots_updated,
                error=error,
            )

        # 返回入库的数据
        return self.db.get_all_attractions()

    def get_stats(self) -> Dict:
        """获取当前数据库统计"""
        return self.db.get_stats()

    def get_high_quality_spots(self, min_quality: float = 0.5) -> List[Dict]:
        """获取高质量景点列表"""
        return self.db.search_attractions(min_quality=min_quality)
