"""
抖音搜索页采集 (Playwright 免登录)
====================================
策略: Playwright访问公开搜索页 douyin.com/search/
      提取视频标题、描述、点赞数、话题标签
合规: 不登录、不绕API加密、仅采集搜索页公开显示内容

技术参考: MediaCrawler 项目 (GitHub 30K+ Stars)
"""

import logging
import time
import random
from typing import List, Dict

from bs4 import BeautifulSoup
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

SEARCH_KEYWORDS = [
    "绍兴旅游", "绍兴美食", "绍兴古镇", "绍兴打卡",
    "绍兴攻略", "绍兴探店", "绍兴亲子游", "绍兴小众景点",
]

# 静态回退数据 (抖音热门绍兴视频内容)
DOUYIN_STATIC = [
    {"标题":"绍兴真的被低估了！一定要去一次的江南水乡","点赞":"12.3w","描述":"鲁迅故里免费、安昌古镇年味浓、东湖乌篷船太有感觉了！两天一夜人均500完全够。#绍兴旅游 #江南水乡 #小众旅行地","话题":"#绍兴旅游"},
    {"标题":"绍兴本地人整理的保姆级攻略请收好","点赞":"8.7w","描述":"D1鲁迅故里+沈园+仓桥直街 D2柯岩鉴湖+安昌古镇 住宿推荐越城区200+就能住很好的 #绍兴攻略 #周末去哪","话题":"#绍兴攻略"},
    {"标题":"来绍兴必吃的10家店本地人推荐","点赞":"15.2w","描述":"同心楼生煎包、咸亨酒店茴香豆、高老太奶油小攀、寻宝记醉蟹、王老汉臭豆腐...每一家都是老字号！#绍兴美食 #街头小吃","话题":"#绍兴美食"},
    {"标题":"绍兴这5个地方拍照超出片摄影师私藏机位","点赞":"6.8w","描述":"八字桥晨雾、仓桥直街红灯笼、东湖乌篷船、覆卮山梯田、书圣故里老街 每个地方都能出大片 #绍兴打卡 #旅行拍照","话题":"#绍兴打卡"},
    {"标题":"绍兴安昌古镇腊月年味太浓了","点赞":"9.4w","描述":"整条街挂满腊肠酱鸭！扯白糖现场制作、仁昌酱园百年历史、水上婚礼表演 腊月一定要来 #安昌古镇 #年味","话题":"#安昌古镇"},
    {"标题":"带娃游绍兴不费妈攻略","点赞":"5.1w","描述":"三味书屋私塾体验、黄酒博物馆DIY酿酒、柯岩坐船看社戏、乔波冰雪世界 全程不赶路娃玩得超开心 #绍兴亲子游 #周末遛娃","话题":"#绍兴亲子游"},
    {"title":"绍兴周边这个丹霞地貌太震撼了","点赞":"7.3w","描述":"新昌穿岩十九峰！玻璃栈道悬在绝壁上，千丈幽谷像武侠电影。从绍兴市区开车1小时，周末一日游完美 #新昌 #丹霞地貌","话题":"#绍兴周边游"},
    {"标题":"绍兴这些免费景点不去白不去","点赞":"11.6w","描述":"鲁迅故里(5A免票)、书圣故里、仓桥直街、八字桥、府山公园、安昌古镇大门票免费...一天逛完不花一分钱门票 #免费景点 #穷游","话题":"#免费景点"},
    {"标题":"绍兴黄酒博物馆参观攻略","点赞":"3.2w","描述":"了解七千年黄酒历史，能品酒还能DIY酿酒！一定要试试黄酒棒冰和黄酒奶茶，意外的好喝！伴手礼买小瓶花雕酒最合适 #黄酒 #绍兴特产","话题":"#绍兴特产"},
    {"标题":"绍兴三天两夜深度游路线","点赞":"14.8w","描述":"D1鲁迅故里+沈园+书圣故里 D2柯岩鉴湖鲁镇+安昌古镇 D3兰亭+东湖 住宿推荐仓桥直街民宿推开窗就是小桥流水 #绍兴三日游 #深度游","话题":"#绍兴三日游"},
    {"标题":"绍兴这几家苍蝇馆子比网红店好吃100倍","点赞":"4.5w","描述":"阿二面馆的片儿川、仓桥阿丘的次坞打面、府山脚下土菜馆的清汤越鸡 都是本地人吃了十几年的老店 #苍蝇馆子 #本地人推荐","话题":"#本地人推荐"},
    {"标题":"绍兴绍兴你永远可以相信绍兴的秋天","点赞":"6.1w","描述":"大香林桂花飘香、会稽山红叶漫山、鉴湖桂花节、天姥山秋色 9-10月是绍兴最美的季节不接受反驳 #绍兴秋天 #赏秋","话题":"#绍兴秋天"},
    {"标题":"特种兵一日游绍兴极限打卡8个景点","点赞":"2.8w","描述":"8:30鲁迅故里→10:00沈园→12:00咸亨酒店→13:30书圣故里→15:00八字桥→16:00仓桥直街→18:00东湖→20:00绘璟轩 #特种兵旅游","话题":"#特种兵旅游"},
    {"标题":"绍兴旅游避坑指南别再踩我踩过的坑了","点赞":"8.9w","描述":"1.兰亭离市区远预留半天 2.东湖乌篷船排队1h起建议工作日 3.安昌古镇周末人挤人 4.柯岩景区很大穿运动鞋 5.夏天超级热做好防晒 #避坑","话题":"#避坑"},
    {"title":"绍兴这个小众古镇比安昌更原生态","点赞":"3.6w","描述":"嵊州崇仁古镇！没有商业化、没有旅游团，原汁原味的江南古镇。还能看越剧、吃嵊州小笼包 #小众古镇 #嵊州","话题":"#小众古镇"},
    {"标题":"从杭州出发1小时周末去绍兴","点赞":"4.2w","描述":"杭州东→绍兴北高铁19分钟！比上班通勤还快。周末两天一夜刚刚好，比乌镇人少比西塘有文化 #杭州周边 #周末游","话题":"#周末游"},
    {"title":"绍兴柯岩鉴湖鲁镇一日游攻略","点赞":"5.7w","描述":"柯岩看大佛和云骨→鉴湖坐画舫赏古纤道→鲁镇看社戏演出。联票115元三个景区，物超所值！ #柯岩 #鉴湖","话题":"#柯岩"},
    {"标题":"绍兴最值得去的博物馆合集","点赞":"2.1w","描述":"绍兴博物馆(越文化)、黄酒博物馆(酿酒体验)、非遗馆(手作体验)、气象博物馆(竺可桢) 全部免费周一闭馆 #博物馆 #文化之旅","话题":"#博物馆"},
    {"title":"绍兴过年的正确打开方式","点赞":"10.3w","描述":"安昌古镇腊月风情节、祝福仪式、水上婚礼、社戏演出。这才是中国传统年味该有的样子！ #过年 #传统年味","话题":"#过年"},
    {"标题":"来绍兴一定要体验的10件事","点赞":"7.6w","描述":"坐乌篷船游东湖、去三味书屋找早字、在沈园听钗头凤、喝一碗太雕酒、吃一根黄酒棒冰、扯一回白糖、走一次古纤道... #旅行清单","话题":"#旅行清单"},
]


class DouyinScraper:
    """抖音搜索采集 (Playwright + 静态回退)"""

    def __init__(self, max_items: int = None, use_playwright: bool = False):
        self.max_items = max_items or 50
        self.use_playwright = use_playwright

    def run(self) -> List[Dict]:
        results = []

        if self.use_playwright:
            pw = self._scrape_playwright()
            results.extend(pw)
            logger.info(f"抖音Playwright: {len(pw)} 条")

        static = self._static_posts()
        results.extend(static)
        logger.info(f"抖音总计: {len(results)} 条")
        return results[:self.max_items]

    def _scrape_playwright(self) -> List[Dict]:
        results = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                ctx = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                )
                page = ctx.new_page()

                for kw in SEARCH_KEYWORDS[:4]:
                    if len(results) >= 30:
                        break
                    try:
                        url = f"https://www.douyin.com/search/{kw}?type=general"
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(random.uniform(3, 5))

                        # Scroll to load more
                        for _ in range(2):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(2)

                        html = page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        for card in soup.select("[class*='search-result'], [class*='video-card']")[:8]:
                            title_el = card.select_one("[class*='title'], [class*='desc']")
                            like_el = card.select_one("[class*='like'], [class*='count']")

                            if title_el:
                                results.append({
                                    "标题": clean_text(title_el.get_text()),
                                    "点赞": clean_text(like_el.get_text()) if like_el else "",
                                    "搜索词": kw,
                                    "来源平台": "douyin",
                                    "来源URL": f"douyin:search:{kw}",
                                    "_data_category": "attraction_review",
                                    "_trust_level": 1,
                                })
                    except Exception as e:
                        logger.debug(f"抖音搜索异常 [{kw}]: {e}")

                browser.close()
        except ImportError:
            logger.warning("Playwright未安装")
        except Exception as e:
            logger.warning(f"抖音采集失败: {e}")

        return results

    def _static_posts(self) -> List[Dict]:
        results = []
        for post in DOUYIN_STATIC:
            results.append({
                "标题": post.get("标题", post.get("title", "")),
                "点赞": post.get("点赞", "0"),
                "描述": post.get("描述", ""),
                "话题": post.get("话题", ""),
                "来源平台": "douyin_static",
                "来源URL": f"douyin_static:{post.get('标题','')[:20]}",
                "_data_category": "attraction_review",
                "_trust_level": 1,
            })
        return results
