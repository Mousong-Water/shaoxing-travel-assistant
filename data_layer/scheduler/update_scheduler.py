"""
定时更新调度器
================================
基于APScheduler的定期数据更新，支持:
  - 启动时检查数据库是否需要初始化
  - 按配置间隔自动爬取更新
  - 更新日志记录
"""

import logging
import time
from datetime import datetime
from typing import Optional, Callable

from shared.config import SchedulerConfig, DatabaseConfig
from data_layer.storage.db_manager import DBManager
from data_layer.scraper.scraper_pipeline import ScraperPipeline
from data_layer.scraper.enrichment_scraper import run_enrichment

logger = logging.getLogger(__name__)


class UpdateScheduler:
    """
    数据更新调度器。

    使用示例:
        scheduler = UpdateScheduler()
        scheduler.start()  # 开始定时更新
        scheduler.run_once()  # 或手动执行一次更新
    """

    def __init__(self, db: DBManager = None):
        self.db = db or DBManager()
        self.pipeline = ScraperPipeline(self.db)
        self._scheduler = None
        self._running = False

    def run_once(self, max_items: int = None) -> dict:
        """
        执行一次完整的更新流程: 爬取 → 清洗 → 入库 → 补充。

        Args:
            max_items: 本次爬取数量上限
        Returns:
            更新结果摘要
        """
        logger.info("=" * 50)
        logger.info(f"开始数据更新 {datetime.now():%Y-%m-%d %H:%M:%S}")
        logger.info("=" * 50)

        start_time = time.time()

        try:
            # Step 1: 爬取并入库
            spots = self.pipeline.run_full(max_items=max_items)
            logger.info(f"爬取入库: {len(spots)} 条")

            # Step 2: 补充季节信息
            enrich_result = run_enrichment(self.db)

            elapsed = time.time() - start_time
            stats = self.db.get_stats()

            result = {
                'success': True,
                'total_spots': stats['total_spots'],
                'high_quality': stats['high_quality_spots'],
                'new_seasonal': enrich_result.get('seasonal', 0),
                'duration_sec': round(elapsed, 1),
                'finished_at': datetime.now().isoformat(),
            }

            logger.info(f"更新完成: {result}")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"更新失败 ({elapsed:.1f}s): {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'duration_sec': round(elapsed, 1),
                'finished_at': datetime.now().isoformat(),
            }

    def _maybe_initialize(self):
        """检查数据库是否为空，为空则首次全量爬取"""
        stats = self.db.get_stats()
        if stats['total_spots'] == 0:
            logger.info("数据库为空，执行首次全量爬取...")
            self.run_once(max_items=50)
        else:
            logger.info(f"数据库已有 {stats['total_spots']} 条数据，跳过首次初始化")

    def start(self, interval_hours: int = None):
        """
        启动定时调度器。

        Args:
            interval_hours: 更新间隔小时数 (默认从config读取)
        """
        if interval_hours is None:
            interval_hours = SchedulerConfig.UPDATE_INTERVAL_HOURS

        if not SchedulerConfig.ENABLE_SCHEDULER:
            logger.info("调度器已禁用 (ENABLE_SCHEDULER=false)，执行一次性初始化")
            self._maybe_initialize()
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            logger.warning("APScheduler未安装，切换到手动模式。请运行 run_once() 或 pip install apscheduler")
            self._maybe_initialize()
            return

        self._scheduler = BackgroundScheduler()
        self._running = True

        # 启动时立即检查
        self._maybe_initialize()

        # 配置定时任务
        self._scheduler.add_job(
            self.run_once,
            'interval',
            hours=interval_hours,
            id='scraper_update',
            name=f'景点数据更新 (每{interval_hours}小时)',
            next_run_time=None,  # 等interval_hours后再执行
        )

        self._scheduler.start()
        logger.info(f"调度器已启动: 每 {interval_hours} 小时更新一次")

    def stop(self):
        """停止定时调度器"""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("调度器已停止")

    def is_running(self) -> bool:
        """检查调度器运行状态"""
        return self._running

    def get_status(self) -> dict:
        """获取调度器状态"""
        stats = self.db.get_stats()
        runs = self.db.get_scraper_runs(limit=5)

        return {
            'scheduler_running': self._running,
            'total_spots': stats['total_spots'],
            'last_update': stats['last_update'],
            'recent_runs': runs,
        }

    def get_last_update_time(self) -> Optional[str]:
        """获取最后一次数据更新时间"""
        stats = self.db.get_stats()
        return stats.get('last_update')


# ============================================================
# 便捷入口
# ============================================================

def run_full_update(max_items: int = None) -> dict:
    """
    执行一次完整数据更新 (便捷函数)。

    Args:
        max_items: 爬取数量上限
    Returns:
        更新结果摘要
    """
    scheduler = UpdateScheduler()
    return scheduler.run_once(max_items=max_items)
