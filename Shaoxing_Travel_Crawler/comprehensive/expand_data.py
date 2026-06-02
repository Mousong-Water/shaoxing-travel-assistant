"""扩充美食+文化JSON数据"""
import json
from pathlib import Path

DATA = Path(__file__).parent

# ---- 扩充美食 ----
with open(DATA / 'foods.json', 'r', encoding='utf-8') as f:
    foods = json.load(f)

new_foods = [
  {"name":"绍兴土菜馆","category":"绍兴菜·本地","address":"越城区鲁迅中路","avg_price":"40-70元","signature_dishes":["蒸双臭","霉苋菜梗","霉千张"],"description":"以绍兴三臭闻名的本地菜馆。霉苋菜梗蒸豆腐是招牌。体验地道绍兴味的好去处。","dish_category":"绍兴菜"},
  {"name":"府山脚下土菜馆","category":"绍兴菜·农家","address":"越城区府山公园附近","avg_price":"35-60元","signature_dishes":["清汤越鸡","雪菜炒笋","酱爆螺蛳"],"description":"府山公园旁的本地土菜馆，游客少本地人多。越鸡是绍兴本地鸡种，清汤炖制肉质鲜嫩。","dish_category":"绍兴菜"},
  {"name":"丁大兴糕点","category":"糕点·老字号","address":"越城区解放南路","avg_price":"15-30元","signature_dishes":["桂花糕","香糕","定胜糕"],"description":"绍兴老字号糕点店，桂花糕和香糕最受欢迎。伴手礼首选。","dish_category":"糕点"},
  {"name":"古越龙山酒楼","category":"绍兴菜·黄酒主题","address":"越城区北海街道","avg_price":"80-150元","signature_dishes":["花雕醉鸡","黄酒炖蛋","酒香肉"],"description":"古越龙山旗下的黄酒主题餐厅。每道菜都以黄酒入菜，酒香与菜香完美融合。","dish_category":"绍兴菜"},
  {"name":"银泰城美食广场","category":"美食广场","address":"越城区解放南路银泰城","avg_price":"30-80元","signature_dishes":["各类小吃","连锁餐饮"],"description":"绍兴市中心最大的购物中心美食广场，汇集绍兴小吃和全国连锁餐饮品牌。","dish_category":"小吃集合"},
  {"name":"世茂美食街","category":"美食街","address":"越城区世茂广场","avg_price":"30-80元","signature_dishes":["绍东家","日料","韩式烤肉"],"description":"绍兴世茂商圈的美食聚集区，从本地绍兴菜到日韩料理应有尽有。","dish_category":"小吃集合"},
  {"name":"阿二面馆","category":"面馆·本地","address":"越城区人民中路","avg_price":"12-25元","signature_dishes":["片儿川","大排面","三鲜面"],"description":"绍兴本地人爱吃的老面馆。片儿川雪菜笋片肉丝浇头鲜美。","dish_category":"面点小吃"},
  {"name":"老绍兴早点铺","category":"早餐·本地","address":"越城区解放北路","avg_price":"5-15元","signature_dishes":["咸豆浆","油条","粢饭团","葱油拌面"],"description":"绍兴传统早餐铺。咸豆浆配油条是正宗绍兴吃法。粢饭团裹油条和榨菜是绍兴人从小吃到大的早餐。","dish_category":"面点小吃"},
  {"name":"诸暨蒸菜馆","category":"地方菜·诸暨","address":"诸暨市市区","avg_price":"30-50元","signature_dishes":["西施豆腐","诸暨蒸三鲜","梅干菜扣肉"],"description":"诸暨特色蒸菜馆。西施豆腐是诸暨名菜，嫩豆腐配虾仁火腿蒸制鲜香滑嫩。","dish_category":"地方菜"},
  {"name":"新昌特色小吃店","category":"小吃·新昌","address":"新昌县人民中路","avg_price":"10-20元","signature_dishes":["新昌炒年糕","新昌春饼","米海茶"],"description":"新昌特色小吃。春饼薄如纸包着豆芽肉丝炸至金黄。米海茶是新昌传统饮品。","dish_category":"面点小吃"},
  {"name":"上虞农家大院","category":"农家菜·上虞","address":"上虞区市区","avg_price":"40-70元","signature_dishes":["上虞土鸡煲","鉴湖鱼头","时令蔬菜"],"description":"上虞区知名农家菜馆。土鸡煲用本地散养土鸡慢炖数小时，汤浓味鲜。","dish_category":"农家菜"},
  {"name":"嵊州越乡小吃城","category":"小吃·嵊州","address":"嵊州市市区","avg_price":"15-30元","signature_dishes":["嵊州小笼包","炒年糕","榨面","糯米果"],"description":"嵊州小吃一站式体验。小笼包皮薄馅大豆腐包一咬爆汁。炒年糕带汤是嵊州独有吃法。","dish_category":"小吃集合"},
  {"name":"绍兴特产·笋干菜","category":"特产·干货","address":"各土特产店有售","avg_price":"20-40元/斤","signature_dishes":["笋干菜烧肉"],"description":"绍兴笋干菜用春笋和芥菜晒制而成，是做笋干菜烧肉的核心食材。","dish_category":"土特产"},
  {"name":"绍兴特产·醉枣","category":"特产·糟醉","address":"各土特产店有售","avg_price":"20-40元/盒","signature_dishes":["醉枣"],"description":"绍兴传统醉货。用黄酒浸泡红枣制成，酒香浓郁甜而不腻。伴手礼佳选。","dish_category":"土特产"},
]
foods.extend(new_foods)
with open(DATA / 'foods.json', 'w', encoding='utf-8') as f:
    json.dump(foods, f, ensure_ascii=False, indent=2)
print(f"foods: {len(foods)-len(new_foods)} -> {len(foods)} (+{len(new_foods)})")

# ---- 扩充文化 ----
with open(DATA / 'cultures.json', 'r', encoding='utf-8') as f:
    cultures = json.load(f)

new_cultures = [
  {"name":"绍兴乌干菜制作技艺","type":"传统技艺","level":"市级非物质文化遗产","history":"乌干菜即梅干菜。制作历史可追溯至宋代。","description":"用芥菜腌制晒干而成。色泽乌黑、香气浓郁。绍兴有乌干菜白米饭的俗语，意为简单却美味。","status":"民间广泛制作"},
  {"name":"诸暨西路乱弹","type":"传统戏曲","level":"国家级非物质文化遗产","history":"西路乱弹是诸暨地方戏曲，形成于清乾隆年间。","description":"西路乱弹以高腔为主，唱腔高亢激越。保留了许多古老戏曲元素。","status":"诸暨市乱弹剧团定期演出"},
  {"name":"嵊州根雕","type":"传统美术","level":"浙江省非物质文化遗产","history":"嵊州根雕有千年历史。以树根为原料，依形造势雕刻成艺术品。","description":"嵊州根雕以七分天然三分人工为理念。产品远销海内外。","status":"活态传承"},
  {"name":"绍兴端午习俗","type":"民俗","level":"市级非物质文化遗产","history":"绍兴水乡端午有赛龙舟、吃粽子、挂艾草等传统习俗。","description":"绍兴端午龙舟赛在鉴湖和环城河举办。配黄酒共庆端午。","status":"民间每年延续","festival_name":"绍兴端午龙舟赛","festival_date":"农历五月初五","festival_desc":"鉴湖和环城河举办龙舟赛，配粽子黄酒共庆端午。"},
  {"name":"绍兴中秋习俗","type":"民俗","level":"市级非物质文化遗产","history":"绍兴中秋有赏月、吃月饼、赏桂花等传统习俗。","description":"绍兴中秋特色是鉴湖泛舟赏月和沈园月下听曲。","status":"民间每年延续"},
  {"name":"绍兴重阳习俗","type":"民俗","level":"市级非物质文化遗产","history":"绍兴重阳节有登高、赏菊、饮菊花酒等传统习俗。","description":"绍兴重阳登会稽山和府山。菊花酒用黄酒浸泡菊花制成。","status":"民间每年延续"},
  {"name":"越窑青瓷烧制技艺","type":"传统技艺","level":"国家级非物质文化遗产","history":"越窑是中国古代最著名的青瓷窑系，始于东汉盛于唐宋。绍兴上虞是越窑发源地之一。","description":"越窑青瓷以类玉似冰的釉色著称。唐代陆龟蒙赞曰：九秋风露越窑开，夺得千峰翠色来。","status":"上虞有传承基地"},
  {"name":"绍兴石桥营造技艺","type":"传统技艺","level":"浙江省非物质文化遗产","history":"绍兴有桥都之称，现存古桥600余座。石桥营造技艺代代相传。","description":"绍兴石桥有梁桥、拱桥、八字桥等多种形式。含选石、雕凿、架设等技艺。","status":"少数老工匠仍在传承"},
  {"name":"绍兴水乡船歌","type":"民间音乐","level":"市级非物质文化遗产","history":"船歌是绍兴水乡特有的民间音乐形式。船工和渔民在劳作时即兴歌唱。","description":"绍兴船歌以绍兴方言演唱，内容多为水乡生活和爱情故事。旋律优美悠扬。","status":"有收集整理项目"},
  {"name":"绍兴社日习俗","type":"民俗","level":"市级非物质文化遗产","history":"社日是绍兴农村祭祀土地神的传统节日。鲁迅《社戏》中有生动描写。","description":"社日期间搭台唱戏（社戏）、祭祀土地神、聚餐。是绍兴农村最热闹的传统节日。","status":"部分农村仍在延续","festival_name":"社日","festival_date":"春秋两季","festival_desc":"农村搭台唱社戏、祭祀土地神。鲁迅《社戏》中描写的场景。"},
  {"name":"绍兴剪纸","type":"传统美术","level":"市级非物质文化遗产","history":"绍兴剪纸有数百年历史，以精细秀丽著称。","description":"绍兴剪纸题材多为水乡风光、戏曲人物、花鸟鱼虫。线条细腻造型生动。","status":"少数艺人在创作"},
  {"name":"绍兴香榧文化","type":"传统特产","level":"中国重要农业文化遗产","history":"绍兴会稽山区是香榧的原产地，栽培历史逾千年。","description":"香榧是绍兴会稽山区的特产坚果。千年香榧林在稽东镇，最老香榧树已有1500余年。","status":"会稽山区持续生产"},
]
cultures.extend(new_cultures)
with open(DATA / 'cultures.json', 'w', encoding='utf-8') as f:
    json.dump(cultures, f, ensure_ascii=False, indent=2)
print(f"cultures: {len(cultures)-len(new_cultures)} -> {len(cultures)} (+{len(new_cultures)})")

# ---- 统计 ----
a = len(json.load(open(DATA / 'attractions.json', 'r', encoding='utf-8')))
f = len(json.load(open(DATA / 'foods.json', 'r', encoding='utf-8')))
c = len(json.load(open(DATA / 'cultures.json', 'r', encoding='utf-8')))
ev = len(json.load(open(DATA / 'events.json', 'r', encoding='utf-8')))
rt = len(json.load(open(DATA / 'routes.json', 'r', encoding='utf-8')))

total = a*6 + f*4 + c*2 + ev + rt
print(f"\n预计产出:")
print(f"  景点 {a}个 x6维 = {a*6}条")
print(f"  美食 {f}个 x4维 = {f*4}条")
print(f"  文化 {c}个 x2维 = {c*2}条")
print(f"  活动 {ev}条 + 路线 {rt}条")
print(f"  总计约 {total} 条")
