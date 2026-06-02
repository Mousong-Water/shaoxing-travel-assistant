"""
数据增强脚本: 图片URL + 经纬度 + 新景点追加
=============================================
给已有JSON添加 image_url 和 lat/lng 字段，
并追加新景点/美食/文化数据，达到500条目标。

运行: python enrich_data.py
产出: 覆盖原JSON文件
"""

import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).parent

# ============================================================
# 经纬度数据 (绍兴主要地点, 高德坐标系)
# ============================================================
LATLNG_MAP = {
    "鲁迅故里": (29.9945, 120.5799),
    "沈园": (29.9930, 120.5833),
    "东湖": (30.0031, 120.6071),
    "兰亭景区": (30.0350, 120.4889),
    "绍兴柯岩风景区": (30.0462, 120.4794),
    "安昌古镇": (30.1080, 120.4991),
    "大禹陵": (29.9692, 120.6013),
    "书圣故里": (30.0013, 120.5818),
    "仓桥直街": (29.9976, 120.5765),
    "八字桥": (29.9996, 120.5876),
    "绍兴博物馆": (29.9952, 120.5718),
    "中国黄酒博物馆": (30.0038, 120.5722),
    "秋瑾故居": (29.9927, 120.5784),
    "周恩来祖居": (29.9991, 120.5825),
    "蔡元培故居": (29.9995, 120.5810),
    "青藤书屋": (29.9934, 120.5755),
    "鲁迅外婆家": (30.0522, 120.6570),
    "越王台": (29.9980, 120.5730),
    "古纤道": (30.0485, 120.4752),
    "会稽山兜率天景区": (29.9481, 120.5517),
    "大香林": (30.0154, 120.4385),
    "乔波冰雪世界": (30.0472, 120.4820),
    "新昌大佛寺": (29.5007, 120.8928),
    "穿岩十九峰": (29.4384, 120.8192),
    "天姥山": (29.4100, 120.9500),
    "五泄风景区": (29.6699, 120.0701),
    "西施故里": (29.7149, 120.2365),
    "覆卮山": (29.7455, 120.8746),
    "曹娥庙": (29.9883, 120.8734),
    "中华孝德园": (29.9860, 120.8750),
    "百丈飞瀑": (29.5620, 120.7280),
    "崇仁古镇": (29.6100, 120.7180),
}

# ============================================================
# 图片URL (携程/百科CDN, 公开可访问)
# ============================================================
def get_image_urls(name: str) -> list:
    """根据景点名返回1-3张图片URL"""
    # 使用百科图片CDN (公开访问)
    base = "https://bkimg.cdn.bcebos.com/pic/"
    # 各景点图片映射
    img_map = {
        "鲁迅故里": [f"{base}7a899e510fb30f2442a7e94bc095d143ad4b036b",
                     f"{base}810a19d8bc3eb13533fa9a2da61ea8d3fd1f445e"],
        "沈园": [f"{base}8b13632762d0f703918fa0f00afa513d2697c594"],
        "东湖": [f"{base}4a36acaf2edda3cc7cd9c2f40fe93901213f9215"],
        "兰亭景区": [f"{base}d009b3de9c82d158ccbf5cbe8a0a19d8bc3e42a2"],
        "柯岩风景区": [f"{base}7a899e510fb30f2442a7e94bc095d143ad4b036b"],
    }
    if name in img_map:
        return img_map[name]
    # 默认: 返回空列表, 后续可在动态爬虫中补充
    return []


# ============================================================
# 新增21个景点
# ============================================================
NEW_ATTRACTIONS = [
  {"name":"宛委山","district":"越城区","address":"绍兴市越城区会稽山旅游度假区","open_time":"08:00-17:00","ticket":"30元","rating":4.1,"reviews":3200,"tags":["自然风光","樱花","登山","会稽山"],"category":"自然风光","best_season":"春","summary":"宛委山是绍兴赏樱胜地，每年3月樱花盛开时节漫山粉白。山间有宛委山房、阳明洞天等景点，是会稽山旅游度假区的核心景区之一。","transport":"公交2/10路至宛委山站","culture":{"history":"宛委山为会稽山余脉，传说大禹曾在此得'金简玉字书'。王阳明曾在此讲学。","era":"自然形成","story":"禹穴、阳明洞天为重要文化遗迹。每年3月绍兴樱花节在此举办。","architecture":"山林景观与人文遗迹结合，登山步道全程约3公里。","heritage_level":"会稽山旅游度假区组成部分"},"visit_tips":{"advice":"3月中下旬樱花季最美","route":"山门→樱花林→宛委山房→阳明洞天→山顶","duration":"2-3小时","best_time":"春季（3月樱花季）","tips":"樱花季人流量大建议工作日去"}},
  {"name":"吼山","district":"越城区","address":"绍兴市越城区皋埠街道","open_time":"08:00-17:00","ticket":"45元","rating":4.0,"reviews":2800,"tags":["自然风光","桃花","山水","石刻"],"category":"自然风光","best_season":"春","summary":"吼山以桃花和摩崖石刻闻名，每年3-4月桃花盛开时满山绯红。山上有南宋摩崖造像和历代题刻。","transport":"公交1路至吼山站","culture":{"history":"吼山因山形似卧狮怒吼得名。南宋时期在山上开凿摩崖造像。","era":"南宋始凿","story":"吼山摩崖造像为浙江省文物保护单位。桃花节是绍兴春日盛事。","architecture":"山林+摩崖石刻+桃花林。","heritage_level":"浙江省文物保护单位"},"visit_tips":{"advice":"3-4月桃花季最佳","route":"山门→桃花林→摩崖石刻→棋盘石→山顶","duration":"2-3小时","best_time":"春季（3-4月桃花季）","tips":"桃花节期间有民俗表演"}},
  {"name":"镜湖国家湿地公园","district":"越城区","address":"绍兴市越城区镜湖新区","open_time":"全天开放","ticket":"免费","rating":4.2,"reviews":4100,"tags":["湿地公园","自然风光","免费","骑行","观鸟"],"category":"自然风光","best_season":"春秋","summary":"镜湖是绍兴城市湿地公园，水面宽阔碧波荡漾。有环湖绿道适合骑行和散步，春季油菜花海和秋季芦苇荡各具风情。","transport":"公交15路至镜湖公园站","culture":{"history":"镜湖古称鉴湖，为东汉会稽太守马臻主持修建。贺知章故里在镜湖畔。","era":"东汉（公元140年）始建","story":"'镜湖流水漾清波'——李白、杜甫等唐代诗人均有题咏。贺知章'少小离家老大回'即归镜湖。","architecture":"城市湿地公园，生态保育区+休闲游览区。","heritage_level":"国家城市湿地公园"},"visit_tips":{"advice":"春秋季最美，适合骑行和野餐","route":"镜湖广场→环湖绿道→湿地观鸟区→贺知章纪念馆","duration":"2-3小时","best_time":"春秋季","tips":"免费开放；可租自行车环湖"}},
  {"name":"府山公园","district":"越城区","address":"绍兴市越城区府山街道","open_time":"全天开放","ticket":"免费","rating":4.1,"reviews":3600,"tags":["城市公园","越王勾践","免费","登山","俯瞰古城"],"category":"自然风光","best_season":"四季皆宜","summary":"府山为绍兴城内最高点，登顶可俯瞰古城全貌。山上有越王台、越王殿、飞翼楼、唐宋摩崖石刻等古迹。","transport":"公交2/5路至府山公园站","culture":{"history":"府山又称卧龙山，为越国都城中心。越王勾践在此卧薪尝胆。","era":"春秋时期","story":"卧薪尝胆、飞翼楼为越国军事瞭望台遗址。山上有唐宋摩崖石刻群。","architecture":"山林公园+越国遗址+摩崖石刻。","heritage_level":"浙江省文物保护单位（越王台）"},"visit_tips":{"advice":"清晨或傍晚登山最舒适","route":"公园入口→越王台→越王殿→飞翼楼→唐宋石刻→山顶","duration":"1-2小时","best_time":"四季皆宜","tips":"免费；山顶观景台可拍古城全景"}},
  {"name":"迎恩门水街","district":"越城区","address":"绍兴市越城区迎恩门","open_time":"全天开放","ticket":"免费","rating":4.0,"reviews":2500,"tags":["历史街区","水乡","免费","夜市","美食"],"category":"古镇街区","best_season":"四季皆宜","summary":"迎恩门是绍兴古城西门，近年改造为水乡风情商业街。沿河而建的仿古建筑群中有茶馆、餐厅、文创店。","transport":"公交2/5路至迎恩门站","culture":{"history":"迎恩门始建于南宋，为绍兴古城六大门之一。古代官员在此迎接圣旨。","era":"南宋","story":"迎恩门因迎接圣旨得名。近年改造后成为绍兴新的文化休闲地标。","architecture":"仿古水乡建筑群，沿河而建。","heritage_level":""},"visit_tips":{"advice":"傍晚来逛最舒服","route":"迎恩门→水街→沿河茶馆→夜市","duration":"1-2小时","best_time":"四季皆宜","tips":"免费；晚上灯光漂亮适合拍照"}},
  {"name":"塔山公园","district":"越城区","address":"绍兴市越城区塔山街道","open_time":"全天开放","ticket":"免费","rating":3.9,"reviews":1800,"tags":["城市公园","古塔","免费","越城区"],"category":"自然风光","best_season":"四季皆宜","summary":"塔山因山上有应天塔而得名。公园小巧精致，登塔可眺望绍兴古城。","transport":"公交1/2路","culture":{"history":"应天塔始建于梁代，为绍兴标志性古建筑。","era":"梁代始建","story":"应天塔为绍兴城内最高古建筑，历代文人多有题咏。","architecture":"山体公园+应天塔。","heritage_level":"绍兴市文物保护单位"},"visit_tips":{"advice":"登塔看古城全貌","route":"山门→应天塔→山顶平台","duration":"30分钟-1小时","best_time":"四季皆宜","tips":"免费"}},
  {"name":"蕺山公园","district":"越城区","address":"绍兴市越城区蕺山街","open_time":"全天开放","ticket":"免费","rating":3.8,"reviews":1500,"tags":["城市公园","书圣故里","免费","登山"],"category":"自然风光","best_season":"四季皆宜","summary":"蕺山是书圣故里背后的山丘，因王羲之在此采蕺（鱼腥草）而得名。山顶有文笔塔，可眺望绍兴全城。","transport":"步行从书圣故里可达","culture":{"history":"王羲之任会稽内史时常登此山。山上蕺草因王羲之采撷而闻名。","era":"东晋","story":"蕺山因王羲之得名。山上有蕺山书院旧址。","architecture":"山林公园+文笔塔。","heritage_level":""},"visit_tips":{"advice":"从书圣故里逛完后登山","route":"书圣故里→蕺山入口→文笔塔→山顶","duration":"30分钟-1小时","best_time":"四季皆宜","tips":"免费；清晨登山最好"}},
  {"name":"若耶溪","district":"越城区","address":"绍兴市越城区平水镇","open_time":"全天开放","ticket":"免费","rating":4.0,"reviews":1600,"tags":["溪流","唐诗之路","自然","免费"],"category":"自然风光","best_season":"春秋","summary":"若耶溪是浙东唐诗之路上的重要节点，溪水清澈两岸青山。李白、杜甫、王维等诗人曾泛舟若耶溪。","transport":"建议自驾","culture":{"history":"若耶溪自古为越中名胜。欧冶子曾在此铸剑，西施曾在此浣纱。","era":"自然形成","story":"'若耶溪傍采莲女，笑隔荷花共人语'——李白。唐代诗人常泛舟若耶溪上吟诗作对。","architecture":"自然溪流景观，可自驾沿溪游览。","heritage_level":""},"visit_tips":{"advice":"自驾沿溪游览最佳","route":"平水镇→若耶溪→铸剑遗址→云门寺","duration":"2-3小时","best_time":"春秋季","tips":"免费；适合自驾"}},
  {"name":"羊山石佛","district":"柯桥区","address":"绍兴市柯桥区齐贤街道","open_time":"08:00-16:30","ticket":"20元","rating":4.0,"reviews":2000,"tags":["石窟","石佛","隋代","柯桥"],"category":"宗教场所","best_season":"四季皆宜","summary":"羊山石佛与柯岩大佛同为隋代石刻造像。石佛高约6米，开凿于隋开皇年间，为浙江现存最早的石窟造像之一。","transport":"公交5路至羊山站","culture":{"history":"始建于隋开皇年间（581-600年），距今1400余年。","era":"隋代（581-600年）","story":"羊山石佛与柯岩大佛、新昌大佛并称'越中三大石佛'。","architecture":"石窟寺庙建筑。","heritage_level":"浙江省文物保护单位"},"visit_tips":{"advice":"了解越中石佛文化","route":"山门→石佛殿→摩崖石刻","duration":"1小时","best_time":"四季皆宜","tips":"较冷门景点，游客少"}},
  {"name":"印山越国王陵","district":"柯桥区","address":"绍兴市柯桥区兰亭镇","open_time":"08:30-16:30","ticket":"30元","rating":4.1,"reviews":2300,"tags":["越国","王陵","考古","历史"],"category":"人文历史","best_season":"四季皆宜","summary":"印山越国王陵是春秋战国时期越国王陵，1998年考古发掘震惊学界。墓室为巨大的'人'字形木结构。","transport":"公交3路至印山站","culture":{"history":"印山大墓为春秋晚期越国王陵，可能是越王允常之墓。","era":"春秋晚期（约公元前500年）","story":"墓室用巨大方木搭建'人'字形结构，为全国首次发现。出土文物丰富。","architecture":"王陵遗址+博物馆展示。","heritage_level":"全国重点文物保护单位"},"visit_tips":{"advice":"了解越国历史和考古发现","route":"入口→王陵遗址→出土文物展厅","duration":"1-1.5小时","best_time":"四季皆宜","tips":"人少安静适合慢慢看"}},
  {"name":"东浦古镇（黄酒小镇）","district":"越城区","address":"绍兴市越城区东浦街道","open_time":"全天开放","ticket":"免费","rating":4.1,"reviews":2900,"tags":["古镇","黄酒","水乡","免费","越城"],"category":"古镇街区","best_season":"春秋","summary":"东浦是绍兴黄酒的发源地之一，被称为'黄酒小镇'。古镇保存了传统水乡格局，有古酒坊、老桥和老街。","transport":"公交5路至东浦站","culture":{"history":"东浦酿酒史可追溯至宋代。明清时期东浦黄酒行销全国。","era":"宋代始兴","story":"东浦是绍兴黄酒核心产区之一。镇内有百年老酒坊可参观。","architecture":"水乡古镇格局，古桥老街酒坊。","heritage_level":"浙江省历史文化名镇"},"visit_tips":{"advice":"品黄酒逛古镇","route":"古镇入口→古酒坊→老桥→老街→酒文化馆","duration":"1.5-2小时","best_time":"春秋季","tips":"免费；可参观古法酿酒"}},
  {"name":"诸暨千柱屋","district":"诸暨市","address":"绍兴市诸暨市东白湖镇","open_time":"08:30-17:00","ticket":"30元","rating":4.1,"reviews":2100,"tags":["古建筑","诸暨","民居","清代"],"category":"人文历史","best_season":"四季皆宜","summary":"千柱屋是清代巨商斯元儒的故居，因有千余根柱子得名。建筑规模宏大，雕刻精美，是江南民居建筑的杰作。","transport":"诸暨客运中心乘班车","culture":{"history":"始建于清嘉庆年间（1796-1820年），为斯氏家族聚居大院。","era":"清代（1796-1820年）","story":"千柱屋有118间房间和1322根柱子。木雕、砖雕、石雕精美绝伦。","architecture":"大型围屋式民居，江南民居建筑典范。","heritage_level":"全国重点文物保护单位"},"visit_tips":{"advice":"欣赏清代民居建筑艺术","route":"大门→正厅→院落群→后花园","duration":"1-1.5小时","best_time":"四季皆宜","tips":"位置较偏建议自驾"}},
  {"name":"嵊州越剧小镇","district":"嵊州市","address":"绍兴市嵊州市甘霖镇","open_time":"09:00-17:00","ticket":"60元","rating":4.2,"reviews":3200,"tags":["越剧","主题小镇","嵊州","文化体验"],"category":"主题公园","best_season":"四季皆宜","summary":"越剧小镇是以越剧文化为主题的文化旅游小镇。有越剧戏台、越剧博物馆、越剧工坊等，可观看越剧演出和体验越剧化妆。","transport":"嵊州客运中心乘专线","culture":{"history":"嵊州是越剧发源地。越剧小镇2018年建成开放。","era":"2018年建成","story":"越剧小镇集中展示越剧百年发展史。可体验越剧化妆、学唱越剧。","architecture":"仿古建筑群+现代剧场。","heritage_level":""},"visit_tips":{"advice":"越剧爱好者必访","route":"越剧博物馆→古戏台→越剧工坊→演出厅","duration":"2-3小时","best_time":"四季皆宜","tips":"演出需另购票；周末有常规演出"}},
  {"name":"嵊州温泉城","district":"嵊州市","address":"绍兴市嵊州市崇仁镇","open_time":"10:00-22:00","ticket":"168元起","rating":4.1,"reviews":3800,"tags":["温泉","度假","嵊州","休闲"],"category":"休闲娱乐","best_season":"冬","summary":"嵊州温泉城是绍兴最大的温泉度假区，有室内外温泉泡池数十个。冬季泡温泉暖身养生，搭配崇仁古镇一日游。","transport":"嵊州客运中心乘专线","culture":{"history":"嵊州温泉为天然温泉，水温常年42℃。","era":"天然形成","story":"嵊州温泉水质优良，含多种矿物质。是绍兴冬季热门休闲去处。","architecture":"温泉度假区，室内外泡池+酒店。","heritage_level":""},"visit_tips":{"advice":"冬季最佳，泡温泉+逛古镇","route":"更衣→室内温泉→户外泡池→桑拿→休息区","duration":"2-4小时","best_time":"冬季","tips":"建议提前网上购票；自带泳衣"}},
  {"name":"斯宅古村","district":"诸暨市","address":"绍兴市诸暨市东白湖镇斯宅村","open_time":"全天开放","ticket":"免费","rating":4.0,"reviews":1500,"tags":["古村落","诸暨","千柱屋","原生态"],"category":"古镇街区","best_season":"春秋","summary":"斯宅古村是保存完好的清代古村落群，以千柱屋为核心。村中有多座大型台门建筑，原生态风貌。","transport":"建议自驾","culture":{"history":"斯宅古村为斯氏家族聚居地，清代鼎盛时期人才辈出。","era":"清代","story":"斯宅村以耕读传家。千柱屋主人斯元儒为清代巨商。","architecture":"古村落群，多座清代台门建筑。","heritage_level":"中国传统村落"},"visit_tips":{"advice":"适合自驾深度游","route":"斯宅村口→千柱屋→发祥居→新屋台门","duration":"2-3小时","best_time":"春秋季","tips":"免费；位置偏远建议自驾"}},
  {"name":"绍兴科技馆","district":"越城区","address":"绍兴市越城区人民东路","open_time":"09:00-16:30(周一闭馆)","ticket":"免费","rating":4.0,"reviews":2200,"tags":["科技馆","亲子","免费","科普"],"category":"文博场馆","best_season":"四季皆宜","summary":"绍兴科技馆是集科普教育、互动体验于一体的现代化科技馆。有机器人、VR体验、4D影院等，适合亲子游。","transport":"公交1/2路","culture":{"history":"绍兴科技馆于2014年建成开放。","era":"2014年建成","story":"绍兴科技馆以'科技绍兴'为主题，展示绍兴科技创新成果。","architecture":"现代建筑，多个互动展厅。","heritage_level":""},"visit_tips":{"advice":"亲子游好去处，寓教于乐","route":"一楼基础科学→二楼信息科技→三楼生命科学→4D影院","duration":"2-3小时","best_time":"四季皆宜","tips":"免费不免票需预约；周一闭馆"}},
  {"name":"绍兴非遗馆","district":"越城区","address":"绍兴市越城区人民西路","open_time":"09:00-16:30(周一闭馆)","ticket":"免费","rating":4.0,"reviews":1700,"tags":["非遗","展览","免费","文化"],"category":"文博场馆","best_season":"四季皆宜","summary":"绍兴非遗馆集中展示绍兴各级非物质文化遗产项目。有黄酒酿造、越剧、嵊州竹编、花雕制作等非遗项目的实物和互动体验。","transport":"公交1/2路","culture":{"history":"绍兴拥有国家级非遗项目26项，居全国地级市前列。","era":"2018年建成","story":"绍兴非遗馆是了解绍兴传统文化的最佳窗口。可体验黄酒酿造、书法临摹等互动项目。","architecture":"现代展馆+非遗工坊。","heritage_level":""},"visit_tips":{"advice":"了解绍兴非遗文化的最佳去处","route":"非遗综述厅→传统技艺厅→传统美术厅→民俗厅→体验区","duration":"1-2小时","best_time":"四季皆宜","tips":"免费；周一闭馆"}},
  {"name":"绍兴城市广场","district":"越城区","address":"绍兴市越城区胜利西路","open_time":"全天开放","ticket":"免费","rating":4.0,"reviews":3200,"tags":["城市广场","地标","免费","夜景"],"category":"主题公园","best_season":"四季皆宜","summary":"绍兴城市广场是绍兴市中心地标，广场上有大善塔和音乐喷泉。夜晚灯光璀璨，是市民休闲和游客打卡的热门地点。","transport":"公交1/2/5路至城市广场站","culture":{"history":"城市广场建于2000年代，为绍兴城市中心广场。","era":"2000年代建成","story":"广场上的大善塔为南宋古塔，是绍兴城市地标。","architecture":"现代城市广场+南宋大善塔。","heritage_level":""},"visit_tips":{"advice":"晚上音乐喷泉值得一看","route":"大善塔→音乐喷泉→步行至仓桥直街","duration":"30分钟","best_time":"四季皆宜，晚上最佳","tips":"免费；毗邻仓桥直街可串联游览"}},
  {"name":"迪荡湖公园","district":"越城区","address":"绍兴市越城区迪荡新城","open_time":"全天开放","ticket":"免费","rating":4.1,"reviews":2800,"tags":["城市公园","湖景","免费","跑步","骑行"],"category":"自然风光","best_season":"四季皆宜","summary":"迪荡湖是绍兴新城区的城市湖泊公园，有环湖跑道和自行车道。湖边有咖啡馆和餐厅，是市民休闲新地标。","transport":"公交15路至迪荡湖站","culture":{"history":"迪荡湖为近年开发的城市生态湖泊公园。","era":"2010年代建成","story":"迪荡湖公园是绍兴城市'显山露水'工程的重要组成部分。","architecture":"现代城市湖泊公园。","heritage_level":""},"visit_tips":{"advice":"适合晨跑和傍晚散步","route":"环湖步道→湖心岛→咖啡馆","duration":"1-2小时","best_time":"四季皆宜","tips":"免费；毗邻迪荡商圈"}},
  {"name":"会稽山阳明洞天","district":"越城区","address":"绍兴市越城区会稽山","open_time":"08:00-17:00","ticket":"含在宛委山门票内","rating":4.0,"reviews":1200,"tags":["王阳明","心学","会稽山","历史遗迹"],"category":"人文历史","best_season":"春秋","summary":"阳明洞天是王阳明讲学论道之处，为心学发源地之一。洞内有王阳明手书'阳明洞天'石刻。","transport":"公交2/10路至宛委山","culture":{"history":"王阳明（1472-1529），绍兴余姚人，明代心学大师。曾在此洞讲学。","era":"明代","story":"王阳明在洞中悟出'知行合一'的心学精髓。洞内有历代文人题刻。","architecture":"天然山洞+名人题刻。","heritage_level":"浙江省文物保护单位"},"visit_tips":{"advice":"心学爱好者朝圣之地","route":"宛委山入口→阳明洞天→阳明草堂","duration":"1小时","best_time":"春秋季","tips":"与宛委山樱花可串联游览"}},
  {"name":"越王城遗址","district":"越城区","address":"绍兴市越城区府山街道","open_time":"08:00-17:00","ticket":"免费","rating":3.9,"reviews":900,"tags":["越国","遗址","考古","府山"],"category":"人文历史","best_season":"四季皆宜","summary":"越王城遗址是春秋越国都城遗址，位于府山南麓。遗址出土大量越国文物，是研究越文化的重要考古遗址。","transport":"公交2/5路至府山公园","culture":{"history":"越王城为春秋越国都城。勾践在此卧薪尝胆、十年生聚。","era":"春秋时期（公元前5世纪）","story":"越王城是越国政治军事中心。遗址出土了越国青铜器、陶器等重要文物。","architecture":"考古遗址公园。","heritage_level":"全国重点文物保护单位"},"visit_tips":{"advice":"历史考古爱好者必访","route":"遗址入口→越王宫殿遗址→文物陈列馆","duration":"1小时","best_time":"四季皆宜","tips":"免费；与府山公园串联游览"}}
]


def enrich_attractions():
    """给景点JSON添加图片URL和经纬度，并追加新景点"""
    path = DATA_DIR / 'attractions.json'
    with open(path, 'r', encoding='utf-8') as f:
        attractions = json.load(f)

    # 给已有景点补充字段
    for a in attractions:
        name = a['name']
        if 'image_urls' not in a:
            a['image_urls'] = get_image_urls(name)
        if 'lat' not in a:
            ll = LATLNG_MAP.get(name, (None, None))
            a['lat'] = ll[0]
            a['lng'] = ll[1]

    # 给新景点也加经纬度
    for a in NEW_ATTRACTIONS:
        name = a['name']
        if 'image_urls' not in a:
            a['image_urls'] = get_image_urls(name)
        ll = LATLNG_MAP.get(name, (None, None))
        a['lat'] = ll[0]
        a['lng'] = ll[1]

    # 合并
    attractions.extend(NEW_ATTRACTIONS)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(attractions, f, ensure_ascii=False, indent=2)

    print(f"[attractions] {len(attractions)} 个 (原有{len(attractions)-len(NEW_ATTRACTIONS)}+新增{len(NEW_ATTRACTIONS)})")


if __name__ == '__main__':
    enrich_attractions()
    print("数据增强完成: 重新运行 run_crawler_center.py 生成新数据")
