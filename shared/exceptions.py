"""
自定义异常类
================================
为各层定义明确的异常类型，便于定位问题。
"""


class TravelAssistantError(Exception):
    """基础异常 - 所有项目异常的父类"""
    def __init__(self, message: str = "", cause: Exception = None):
        super().__init__(message)
        self.cause = cause


# ---- 数据层异常 ----
class DataLayerError(TravelAssistantError):
    """数据层异常基类"""

class ScraperError(DataLayerError):
    """爬虫异常"""

class ScraperBlockedError(ScraperError):
    """爬虫被WAF/反爬拦截"""

class ScraperEmptyError(ScraperError):
    """爬虫返回空结果"""

class DatabaseError(DataLayerError):
    """数据库异常"""

class DataQualityError(DataLayerError):
    """数据质量异常"""


# ---- 智能体层异常 ----
class AgentLayerError(TravelAssistantError):
    """智能体层异常基类"""

class ModelError(AgentLayerError):
    """模型调用异常"""

class ModelAuthError(ModelError):
    """模型认证失败 (API Key无效)"""

class ModelRateLimitError(ModelError):
    """模型调用频率限制"""

class RAGError(AgentLayerError):
    """RAG检索异常"""

class PlanningError(AgentLayerError):
    """路线规划异常"""

class ProfileError(AgentLayerError):
    """用户画像异常"""


# ---- 前端层异常 ----
class FrontendError(TravelAssistantError):
    """前端层异常基类"""
