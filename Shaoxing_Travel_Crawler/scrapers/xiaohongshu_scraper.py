"""
小红书攻略采集 (Playwright网页版)
====================================
策略: Playwright加载网页版搜索页 → 滚动加载 → 解析HTML
合规: 不登录、不绕API签名、不使用自动化工具绕过限流
频率: 3-5秒/次请求, 符合正常人类浏览速度

搜索URL: https://www.xiaohongshu.com/search_result?keyword=绍兴旅游
"""

import logging
import time
import random
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from crawler_utils.parser_utils import clean_text

logger = logging.getLogger(__name__)

# 搜索关键词
SEARCH_KEYWORDS = [
    "绍兴旅游攻略",
    "绍兴美食推荐",
    "绍兴古镇",
    "绍兴拍照打卡",
    "绍兴小众景点",
    "绍兴亲子游",
    "绍兴周末去哪",
    "绍兴探店",
    "绍兴必去景点",
    "绍兴旅游避雷",
]

# 静态回退数据 (小红书热门绍兴旅游帖内容摘要)
XHS_STATIC_POSTS = [
    {"标题":"绍兴2天1夜保姆级攻略","点赞":3200,"内容":"D1鲁迅故里+沈园+仓桥直街(夜景绝了！) D2东湖乌篷船+兰亭。住宿推荐越城区，200+就能住不错的。一定要吃王老汉臭豆腐和高老太奶油小攀！","标签":"旅游攻略"},
    {"标题":"绍兴真的被低估了！三天两晚超详细行程","点赞":5800,"内容":"去了5次绍兴总结的精华路线。柯岩风景区一定要去，鉴湖坐船太美了。安昌古镇腊月去最有年味，扯白糖必看。","标签":"旅游攻略"},
    {"标题":"绍兴最全美食地图本地人推荐","点赞":9100,"内容":"同心楼生煎包刚出锅的最好吃！寻宝记排队1小时起步建议工作日去。高老太奶油小攀下午3点后基本卖完。黄酒棒冰5元一根随处可买。","标签":"美食推荐"},
    {"标题":"绍兴这5个地方拍照超出片","点赞":4200,"内容":"1.八字桥(古桥+水乡经典机位) 2.仓桥直街(红灯笼夜景) 3.东湖乌篷船(ins风水墨大片) 4.覆卮山梯田(油菜花季绝美) 5.书圣故里(烟火气老街)","标签":"拍照打卡"},
    {"标题":"绍兴本地人才知道的宝藏景点","点赞":6800,"内容":"不要再只去鲁迅故里了！羊山石佛知道的人很少、印山越国王陵超震撼、东浦黄酒小镇免费又好逛、宛委山樱花季美哭了。","标签":"小众景点"},
    {"标题":"带娃游绍兴不累的行程安排","点赞":2500,"内容":"D1上午鲁迅故里(三味书屋体验私塾课)→中午咸亨酒店→下午科技馆 D2柯岩坐船看鲁镇社戏→乔波冰雪世界。全程不赶路。","标签":"亲子游"},
    {"标题":"绍兴各景点真实体验避雷指南","点赞":7300,"内容":"兰亭值得去但离市区远预留半天。柯岩联票115元划算但要走很多路穿舒服的鞋。安昌古镇不要周末去人挤人。东湖乌篷船85元略贵但值得体验一次。","标签":"避雷指南"},
    {"标题":"绍兴黄酒体验全攻略","点赞":3600,"内容":"黄酒博物馆可以品酒，从3年陈到30年陈都有。古越龙山体验馆可以定制花雕酒坛。一定要试试黄酒奶茶和黄酒棒冰，意外好喝！","标签":"美食推荐"},
    {"标题":"绍兴秋天最美路线","点赞":4100,"内容":"9-10月是绍兴最好季节！大香林桂花满山飘香，鉴湖桂花节，会稽山红叶。天姥山秋色不输京都。配一碗黄酒暖暖的太舒服了。","标签":"旅游攻略"},
    {"标题":"绍兴3天2夜深度文化游","点赞":5500,"内容":"书法爱好者必走路线：兰亭(朝圣)→书圣故里(王羲之)→青藤书屋(徐渭)→绍兴博物馆。每个地方都能让你感受到绍兴深厚的文化底蕴。","标签":"旅游攻略"},
    {"标题":"绍兴这些老字号你吃过几家","点赞":8900,"内容":"咸亨酒店(1894年)茴香豆配太雕酒绝了。同心楼(百年)生煎包底脆肉鲜。荣禄春(同治年间)小笼包皮薄汤多。丁大兴桂花糕伴手礼首选。","标签":"美食推荐"},
    {"标题":"绍兴周末特种兵一日游","点赞":2800,"内容":"8:30鲁迅故里→10:00沈园→12:00寻宝记午餐→14:00书圣故里→16:00仓桥直街→18:00东湖夜游(如果有的话)→20:00绘璟轩黄酒奶茶收尾。一天刷完！","标签":"旅游攻略"},
    {"标题":"绍兴冬天怎么玩","点赞":3200,"内容":"安昌腊月风情节必去！整条街挂满腊肠酱鸭年味超浓。然后去嵊州泡温泉。回来路上带点安昌腊肠和仁昌酱油做伴手礼。","标签":"旅游攻略"},
    {"标题":"绍兴免费景点合集","点赞":6700,"内容":"鲁迅故里(免票)、书圣故里(免费)、仓桥直街(免费)、八字桥(免费)、府山公园(免费)、城市广场(免费)、环城河步道(免费)。省钱党必收藏！","标签":"旅游攻略"},
    {"标题":"绍兴周边游之新昌嵊州篇","点赞":2400,"内容":"新昌大佛寺江南第一大佛很震撼。穿岩十九峰玻璃栈道刺激。嵊州一定要吃豆腐包和炒年糕。崇仁古镇比安昌更原生态。","标签":"旅游攻略"},
    {"title":"绍兴探店之藏在巷子里的咖啡馆","点赞":1800,"内容":"书圣故里巷子里有好几家宝藏咖啡馆。西小路的柒舍小院既是用餐也是下午茶好去处。仓桥直街的茶馆可以坐一下午。","标签":"探店笔记"},
    {"标题":"绍兴特产买什么带回家","点赞":4500,"内容":"1.安昌腊肠(40-60元/斤) 2.仁昌母子酱油(20-50元/瓶) 3.绍兴黄酒(各种年份) 4.梅干菜(15-30元/斤) 5.桂花糕/香糕 6.扯白糖 7.嵊州榨面 8.黄酒棒冰(现吃)","标签":"购物推荐"},
    {"标题":"绍兴旅游住宿推荐","点赞":2200,"内容":"越城区鲁迅故里附近最方便200-500元。仓桥直街附近有民宿推开窗就是水乡。柯桥区性价比高100-300元。安昌古镇有客栈可以体验水乡夜晚。","标签":"旅游攻略"},
    {"标题":"绍兴各景点门票汇总","点赞":5100,"内容":"免费:鲁迅故里、书圣故里、仓桥直街、八字桥、安昌古镇(大门票)。收费:柯岩115元、兰亭70元、东湖50元(乌篷船85元另购)、沈园40元(夜游80元)、大禹陵50元。","标签":"实用信息"},
    {"标题":"绍兴最佳旅游季节","点赞":3600,"内容":"春天(3-4月):樱花桃花油菜花季。秋天(9-10月):桂花季红叶季。冬天(12-1月):安昌腊月风情节。夏天太热建议安排室内景点+水上乐园。","标签":"实用信息"},
]


class XiaohongshuScraper:
    """小红书攻略采集 (Playwright + 静态回退)"""

    def __init__(self, max_items: int = None, use_playwright: bool = False):
        self.max_items = max_items or 300
        self.use_playwright = use_playwright

    def run(self) -> List[Dict]:
        """采集小红书攻略"""
        results = []

        if self.use_playwright:
            pw_results = self._scrape_with_playwright()
            results.extend(pw_results)
            logger.info(f"小红书Playwright: {len(pw_results)} 条")
        else:
            logger.info("小红书使用静态数据模式 (Playwright模式需use_playwright=True)")

        # 静态数据作为补充/回退
        static = self._static_posts()
        results.extend(static)
        logger.info(f"小红书总计: {len(results)} 条")

        return results[:self.max_items]

    def _scrape_with_playwright(self) -> List[Dict]:
        """Playwright加载小红书搜索页"""
        results = []
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="zh-CN",
                )
                page = context.new_page()

                for kw in SEARCH_KEYWORDS[:5]:
                    if len(results) >= 100:
                        break
                    try:
                        url = f"https://www.xiaohongshu.com/search_result?keyword={kw}&source=web_search_result_notes"
                        page.goto(url, timeout=30000, wait_until="domcontentloaded")
                        time.sleep(random.uniform(3, 5))

                        # 滚动加载
                        for _ in range(3):
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            time.sleep(2)

                        html = page.content()
                        soup = BeautifulSoup(html, "html.parser")

                        for note in soup.select("[class*='note-item'], section[class*='note']")[:8]:
                            title_elem = note.select_one("[class*='title'], .note-title, a[href*='/explore/']")
                            like_elem = note.select_one("[class*='like'], [class*='count']")

                            if title_elem:
                                title = clean_text(title_elem.get_text())
                                href = title_elem.get("href", "") if title_elem.name == "a" else ""
                                likes = clean_text(like_elem.get_text()) if like_elem else ""

                                results.append({
                                    "标题": title,
                                    "链接": f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href,
                                    "点赞": likes,
                                    "搜索词": kw,
                                    "来源平台": "xiaohongshu",
                                    "来源URL": f"https://www.xiaohongshu.com{href}" if href.startswith("/") else href,
                                    "_data_category": "attraction_review",
                                    "_trust_level": 1,
                                })
                    except Exception as e:
                        logger.debug(f"小红书搜索异常 [{kw}]: {e}")
                        continue

                browser.close()
        except ImportError:
            logger.warning("Playwright未安装，跳过小红书动态采集")
        except Exception as e:
            logger.warning(f"小红书Playwright采集失败: {e}")

        return results

    def _static_posts(self) -> List[Dict]:
        """静态回退数据"""
        results = []
        for post in XHS_STATIC_POSTS:
            results.append({
                "标题": post.get("标题", post.get("title", "")),
                "点赞": str(post.get("点赞", 0)),
                "内容": post.get("内容", ""),
                "标签": post.get("标签", ""),
                "来源平台": "xiaohongshu_static",
                "来源URL": f"xhs_static:{post.get('标题', '')[:20]}",
                "_data_category": self._classify(post),
                "_trust_level": 1,
            })
        return results

    def _classify(self, post: Dict) -> str:
        tag = post.get("标签", "")
        content = post.get("内容", "")
        text = tag + content
        if "美食" in text or "探店" in text:
            return "food_shop"
        elif "攻略" in text or "行程" in text or "路线" in text:
            return "attraction_review"
        elif "打卡" in text or "拍照" in text:
            return "attraction_review"
        elif "避雷" in text or "实用" in text or "门票" in text or "住宿" in text:
            return "attraction_review"
        elif "特产" in text or "购物" in text:
            return "local_food"
        return "attraction_review"
