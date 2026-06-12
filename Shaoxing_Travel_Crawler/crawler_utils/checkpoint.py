"""
断点续爬模块
============
保存爬取进度到JSON文件，中断后从上次位置继续。

使用:
    cp = Checkpoint("douyin_search")

    for kw in keywords:
        if cp.is_done(kw):
            continue  # 跳过已完成的关键词
        results = scrape(kw)
        cp.mark_done(kw, count=len(results))

    cp.summary()  # 打印进度摘要
"""

import json
import time
from pathlib import Path
from typing import Set, Optional


class Checkpoint:
    """断点续爬管理器"""

    def __init__(self, name: str, save_dir: Path = None):
        """
        Args:
            name: 爬虫名称 (如 'douyin_search')
            save_dir: 保存目录 (默认 crawler/checkpoints/)
        """
        self.name = name
        self.save_dir = save_dir or Path(__file__).parent.parent / 'checkpoints'
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._path = self.save_dir / f'{name}_checkpoint.json'
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            with open(self._path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "name": self.name,
            "created_at": time.time(),
            "completed": [],    # 已完成的关键词/URL列表
            "total_items": 0,   # 已采集总数
            "last_run": None,   # 上次运行时间
        }

    def _save(self):
        self._data["last_run"] = time.time()
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def is_done(self, key: str) -> bool:
        """检查某个关键词/URL是否已完成"""
        return key in self._data["completed"]

    def mark_done(self, key: str, count: int = 0):
        """标记完成"""
        if key not in self._data["completed"]:
            self._data["completed"].append(key)
        self._data["total_items"] += count
        self._save()

    def reset(self):
        """重置进度"""
        self._data["completed"] = []
        self._data["total_items"] = 0
        self._save()

    def get_remaining(self, all_keys: list) -> list:
        """获取未完成的关键词列表"""
        return [k for k in all_keys if not self.is_done(k)]

    def summary(self) -> str:
        completed = len(self._data["completed"])
        return f"[{self.name}] 已完成:{completed} 采集:{self._data['total_items']}条"

    @property
    def completed_count(self) -> int:
        return len(self._data["completed"])

    @property
    def total_collected(self) -> int:
        return self._data["total_items"]
