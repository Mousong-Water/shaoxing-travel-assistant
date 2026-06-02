"""
爬虫基类
================================
定义所有爬虫必须实现的接口，提供通用工具方法。
"""

import random
import re
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from shared.config import ScraperConfig, RAW_DATA_DIR
from shared.logging_config import logger
from shared.exceptions import ScraperError, ScraperBlockedError, ScraperEmptyError


class BaseScraper(ABC):
    """爬虫抽象基类"""

    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self.session = requests.Session()

    # ---- 工具方法 ----

    @staticmethod
    def random_ua() -> str:
        """从UA池随机选取User-Agent"""
        return random.choice(ScraperConfig.USER_AGENTS)

    @staticmethod
    def clean_text(text: str) -> str:
        """清洗文本: 合并空白、去除首尾空格"""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @staticmethod
    def safe_find(soup: BeautifulSoup, selectors: list, default: str = "") -> str:
        """按优先级尝试多个CSS选择器提取文本"""
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                text = BaseScraper.clean_text(elem.get_text())
                if text:
                    return text
        return default

    def _request(self, url: str, cookies: dict = None,
                 referer: str = None, timeout: int = None) -> requests.Response:
        """
        发送GET请求，含重试逻辑和UA轮换。

        Args:
            url: 目标URL
            cookies: Cookie字典
            referer: Referer头
            timeout: 超时秒数
        Returns:
            requests.Response对象
        Raises:
            ScraperBlockedError: 连续被拦截
            ScraperError: 其他请求失败
        """
        timeout = timeout or self.config.REQUEST_TIMEOUT
        headers = {
            'User-Agent': self.random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        if referer:
            headers['Referer'] = referer

        last_error = None
        for attempt in range(self.config.MAX_RETRIES):
            try:
                resp = self.session.get(url, headers=headers, cookies=cookies,
                                        timeout=timeout)
                resp.encoding = 'utf-8'

                if resp.status_code == 200 and len(resp.text) > 1000:
                    return resp

                if resp.status_code == 403 or len(resp.text) < 500:
                    logger.warning(f"请求被拦截 (尝试{attempt+1}/{self.config.MAX_RETRIES}): "
                                   f"status={resp.status_code}, len={len(resp.text)}")
                    last_error = ScraperBlockedError(f"被拦截: {url}")

            except requests.RequestException as e:
                logger.warning(f"请求失败 (尝试{attempt+1}/{self.config.MAX_RETRIES}): {e}")
                last_error = ScraperError(f"请求异常: {e}")

            if attempt < self.config.MAX_RETRIES - 1:
                wait = self.config.RETRY_BACKOFF ** (attempt + 1)
                time.sleep(wait)

        if last_error:
            raise last_error
        raise ScraperError(f"请求失败: {url}")

    def random_delay(self):
        """随机延迟，降低请求频率"""
        delay = random.uniform(self.config.DELAY_MIN, self.config.DELAY_MAX)
        time.sleep(delay)

    # ---- 子类必须实现的接口 ----

    @abstractmethod
    def fetch_list(self, page: int = 1) -> List[Dict]:
        """
        爬取列表页，返回景点摘要列表。

        Args:
            page: 页码 (1-based)
        Returns:
            [{'name': str, 'url': str, ...}, ...]
        """
        ...

    @abstractmethod
    def fetch_detail(self, url: str, name: str) -> Dict:
        """
        爬取详情页，返回完整景点信息。

        Args:
            url: 详情页URL
            name: 景点名称 (备用)
        Returns:
            包含所有提取字段的字典
        """
        ...

    @abstractmethod
    def run(self, max_items: int = None) -> List[Dict]:
        """执行爬取流程"""
        ...
