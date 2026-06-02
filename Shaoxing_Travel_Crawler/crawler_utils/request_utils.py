"""
公共请求工具
================================
从 shaoxing_scraper.py 中抽取的通用请求逻辑，所有爬虫共用。
解决短板: #1 #5 #7 #8 (请求散落、无重试、无频控、响应码无分类)
"""

import random
import time
import requests
from typing import Dict, Optional, Tuple


# ============================================================
# UA池 (从原文件 L50-56 抽取)
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def random_ua() -> str:
    """随机选取User-Agent (原 L63-64)"""
    return random.choice(USER_AGENTS)


# ============================================================
# 响应码分类 (新增 - 解决短板 #8)
# ============================================================

def classify_response(resp: requests.Response) -> str:
    """
    分类HTTP响应状态，返回可操作的标签。

    Returns:
        'ok'       - 200 且内容充足
        'blocked'  - 403/406 反爬拦截
        'rate'     - 429 频率限制
        'server'   - 5xx 服务端错误
        'empty'    - 200 但内容过短(疑似被静默拦截)
        'unknown'  - 其他状态码
    """
    code = resp.status_code
    length = len(resp.text) if resp.text else 0

    if code == 200 and length > 1000:
        return 'ok'
    if code in (403, 406):
        return 'blocked'
    if code == 429:
        return 'rate'
    if 500 <= code < 600:
        return 'server'
    if code == 200 and length < 500:
        return 'empty'
    return 'unknown'


# ============================================================
# 请求管理器 (新增 - 解决短板 #5 #7)
# ============================================================

class RequestManager:
    """
    统一请求管理器: Session复用、自动重试、频率控制、Cookie管理。

    使用方式:
        rm = RequestManager()
        resp = rm.get(url, cookies=..., referer=...)
    """

    def __init__(
        self,
        delay_min: float = 2.0,
        delay_max: float = 4.0,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
        timeout: int = 30,
    ):
        """
        Args:
            delay_min: 请求最小间隔(秒)
            delay_max: 请求最大间隔(秒)
            max_retries: 最大重试次数
            retry_backoff: 重试退避倍数 (2=2s,4s,8s)
            timeout: 请求超时(秒)
        """
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.timeout = timeout

        self.session = requests.Session()
        self._last_request_time = 0
        self._request_count = 0

    # ---- 频率控制 ----

    def wait(self):
        """随机延时，控制请求频率 (原 L470 的DELAY逻辑)"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _auto_delay(self):
        """自动延时：根据距上次请求的间隔决定是否等待"""
        elapsed = time.time() - self._last_request_time
        min_gap = self.delay_min * 0.5  # 最小间隔

        if elapsed < min_gap:
            wait_time = min_gap - elapsed + random.uniform(0, 1)
            time.sleep(wait_time)

    # ---- 请求头组装 (原 L206-213) ----

    def _build_headers(self, referer: str = None, extra: dict = None) -> dict:
        """组装请求头"""
        headers = {
            'User-Agent': random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
        if referer:
            headers['Referer'] = referer
        if extra:
            headers.update(extra)
        return headers

    # ---- 核心请求方法 ----

    def get(
        self,
        url: str,
        cookies: dict = None,
        referer: str = None,
        headers_extra: dict = None,
        timeout: int = None,
    ) -> Tuple[Optional[requests.Response], str]:
        """
        发送GET请求，含自动重试和频率控制。

        Args:
            url: 目标URL
            cookies: Cookie字典
            referer: Referer
            headers_extra: 额外请求头
            timeout: 超时秒数(默认使用实例配置)

        Returns:
            (response, status_tag)
            - response: 成功返回Response对象，失败返回None
            - status_tag: 'ok'/'blocked'/'rate'/'server'/'empty'/'unknown'/'error'

        使用示例:
            resp, tag = rm.get(url, cookies=cookies, referer=list_url)
            if tag == 'ok':
                html = resp.text
            elif tag == 'blocked':
                # 触发Playwright回退
                ...
        """
        timeout = timeout or self.timeout
        headers = self._build_headers(referer=referer, extra=headers_extra)
        last_tag = 'error'

        for attempt in range(self.max_retries):
            # 频率控制 (首次请求也检查间隔)
            if self._request_count > 0:
                self._auto_delay()

            try:
                resp = self.session.get(url, headers=headers, cookies=cookies,
                                        timeout=timeout)
                resp.encoding = 'utf-8'
                self._last_request_time = time.time()
                self._request_count += 1

                tag = classify_response(resp)
                if tag == 'ok':
                    return resp, tag
                if tag == 'blocked':
                    return None, tag  # 反爬拦截不重试
                if tag == 'rate':
                    # 频率限制: 等待更长时间后重试
                    wait = self.retry_backoff ** (attempt + 1) * 2
                    time.sleep(wait)
                    last_tag = tag
                    continue
                if tag == 'server':
                    # 服务端错误: 短暂等待后重试
                    if attempt < self.max_retries - 1:
                        time.sleep(self.retry_backoff ** (attempt + 1))
                    last_tag = tag
                    continue
                if tag == 'empty':
                    return resp, tag  # 静默拦截但返回响应体供调试
                # unknown: 也返回响应体供调用方判断
                return resp, tag

            except requests.Timeout:
                last_tag = 'timeout'
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff ** (attempt + 1))
            except requests.ConnectionError:
                last_tag = 'connection_error'
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff ** (attempt + 1))
            except requests.RequestException as e:
                last_tag = 'error'
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_backoff ** (attempt + 1))

        return None, last_tag

    def test_cookies(self, url: str, cookies: dict, referer: str = None) -> bool:
        """快速测试Cookie是否有效"""
        resp, tag = self.get(url, cookies=cookies, referer=referer, timeout=15)
        return tag == 'ok'

    @property
    def stats(self) -> dict:
        """请求统计"""
        return {
            'request_count': self._request_count,
            'last_request_time': self._last_request_time,
        }
