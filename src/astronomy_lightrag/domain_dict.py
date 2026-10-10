"""
domain_dict.py
Comprehensive Astronomical Domain Vocabulary & Knowledge Base Dictionary.

Combines:
1. All 110 Messier Objects (M1 - M110) with NGC numbers & bilingual names.
2. All 109 Caldwell Objects (C1 - C109) with NGC/IC numbers & bilingual names.
3. All 88 IAU Constellations (3-letter codes, English, Chinese standard names).
4. Major Deep-Sky Objects & Common Observational Equipment (Filters, Telescopes).
5. Fast in-memory alias lookup and reverse index.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger("astronomy_lightrag.domain_dict")

# Directory of this module
CURRENT_DIR = Path(__file__).resolve().parent
DICT_JSON_PATH = CURRENT_DIR / "domain_dict.json"

# ── 1. All 110 Messier Objects ──────────────────────────────────────────────
MESSIER_CATALOG: Dict[str, Dict[str, List[str]]] = {
    "M1": {"ngc": ["NGC 1952"], "en": ["Crab Nebula", "Taurus A"], "cn": ["蟹状星云"]},
    "M2": {"ngc": ["NGC 7089"], "en": ["Aquarius Cluster"], "cn": ["宝瓶座球状星团"]},
    "M3": {"ngc": ["NGC 5272"], "en": ["Canes Venatici Cluster"], "cn": ["猎犬座球状星团"]},
    "M4": {"ngc": ["NGC 6121"], "en": ["Cat's Eye Cluster"], "cn": ["天蝎座球状星团"]},
    "M5": {"ngc": ["NGC 5904"], "en": ["Rose Cluster"], "cn": ["巨蛇座球状星团"]},
    "M6": {"ngc": ["NGC 6405"], "en": ["Butterfly Cluster"], "cn": ["蝴蝶星团"]},
    "M7": {"ngc": ["NGC 6475"], "en": ["Ptolemy's Cluster"], "cn": ["托勒密星团"]},
    "M8": {"ngc": ["NGC 6523"], "en": ["Lagoon Nebula"], "cn": ["礁湖星云"]},
    "M9": {"ngc": ["NGC 6333"], "en": ["Globular Cluster in Ophiuchus"], "cn": ["蛇夫座球状星团"]},
    "M10": {"ngc": ["NGC 6254"], "en": ["Globular Cluster in Ophiuchus"], "cn": ["蛇夫座球状星团"]},
    "M11": {"ngc": ["NGC 6705"], "en": ["Wild Duck Cluster"], "cn": ["野鸭星团"]},
    "M12": {"ngc": ["NGC 6218"], "en": ["Gumball Globular"], "cn": ["蛇夫座球状星团"]},
    "M13": {"ngc": ["NGC 6205"], "en": ["Great Hercules Cluster"], "cn": ["武仙座大星团"]},
    "M14": {"ngc": ["NGC 6402"], "en": ["Globular Cluster in Ophiuchus"], "cn": ["蛇夫座球状星团"]},
    "M15": {"ngc": ["NGC 7078"], "en": ["Great Pegasus Cluster"], "cn": ["飞马座球状星团"]},
    "M16": {"ngc": ["NGC 6611"], "en": ["Eagle Nebula", "Pillars of Creation", "Star Queen"], "cn": ["鹰状星云", "创生之柱"]},
    "M17": {"ngc": ["NGC 6618"], "en": ["Omega Nebula", "Swan Nebula", "Horseshoe Nebula"], "cn": ["奥米加星云", "天鹅星云"]},
    "M18": {"ngc": ["NGC 6613"], "en": ["Black Swan Cluster"], "cn": ["黑天鹅星团"]},
    "M19": {"ngc": ["NGC 6273"], "en": ["Oblate Globular Cluster"], "cn": ["天蝎座扁球状星团"]},
    "M20": {"ngc": ["NGC 6514"], "en": ["Trifid Nebula"], "cn": ["三叶星云"]},
    "M21": {"ngc": ["NGC 6531"], "en": ["Webb's Cross"], "cn": ["人马座疏散星团"]},
    "M22": {"ngc": ["NGC 6656"], "en": ["Great Sagittarius Cluster"], "cn": ["人马座大球状星团"]},
    "M23": {"ngc": ["NGC 6494"], "en": ["Bat Motif Cluster"], "cn": ["人马座疏散星团"]},
    "M24": {"ngc": ["IC 4715"], "en": ["Small Sagittarius Star Cloud", "Delle Caustiche"], "cn": ["小人马恒星云"]},
    "M25": {"ngc": ["IC 4725"], "en": ["Open Cluster in Sagittarius"], "cn": ["人马座疏散星团"]},
    "M26": {"ngc": ["NGC 6694"], "en": ["Open Cluster in Scutum"], "cn": ["盾牌座疏散星团"]},
    "M27": {"ngc": ["NGC 6853"], "en": ["Dumbbell Nebula", "Apple Core Nebula"], "cn": ["哑铃星云"]},
    "M28": {"ngc": ["NGC 6626"], "en": ["Globular Cluster in Sagittarius"], "cn": ["人马座球状星团"]},
    "M29": {"ngc": ["NGC 6913"], "en": ["Cooling Tower Cluster"], "cn": ["天鹅座疏散星团"]},
    "M30": {"ngc": ["NGC 7099"], "en": ["Globular Cluster in Capricornus"], "cn": ["摩羯座球状星团"]},
    "M31": {"ngc": ["NGC 224"], "en": ["Andromeda Galaxy", "Great Andromeda Galaxy", "Great Spiral Nebula in Andromeda"], "cn": ["仙女座大星系", "仙女座大星云"]},
    "M32": {"ngc": ["NGC 221"], "en": ["Le Gentil Companion", "Dwarf Elliptical Galaxy"], "cn": ["仙女座伴星系", "椭圆矮星系"]},
    "M33": {"ngc": ["NGC 598"], "en": ["Triangulum Galaxy", "Pinwheel Galaxy"], "cn": ["三角座星系", "风车星系"]},
    "M34": {"ngc": ["NGC 1039"], "en": ["Spiral Cluster"], "cn": ["英仙座疏散星团"]},
    "M35": {"ngc": ["NGC 2168"], "en": ["Open Cluster in Gemini"], "cn": ["双子座疏散星团"]},
    "M36": {"ngc": ["NGC 1960"], "en": ["Pinwheel Cluster"], "cn": ["御夫座疏散星团"]},
    "M37": {"ngc": ["NGC 2099"], "en": ["Auriga Salt-and-Pepper Cluster"], "cn": ["御夫座疏散星团"]},
    "M38": {"ngc": ["NGC 1912"], "en": ["Starfish Cluster"], "cn": ["海星星团"]},
    "M39": {"ngc": ["NGC 7092"], "en": ["Open Cluster in Cygnus"], "cn": ["天鹅座疏散星团"]},
    "M40": {"ngc": ["Winnecke 4"], "en": ["Winnecke 4", "75 Ursae Majoris Double Star"], "cn": ["大熊座双星", "温内克4"]},
    "M41": {"ngc": ["NGC 2287"], "en": ["Little Beehive Cluster"], "cn": ["大犬座疏散星团"]},
    "M42": {"ngc": ["NGC 1976"], "en": ["Great Orion Nebula", "Trapezium Nebula"], "cn": ["猎户座大星云", "猎户四边形星云"]},
    "M43": {"ngc": ["NGC 1982"], "en": ["De Mairan's Nebula"], "cn": ["德梅兰星云"]},
    "M44": {"ngc": ["NGC 2632"], "en": ["Beehive Cluster", "Praesepe"], "cn": ["鬼星团", "蜂巢星团"]},
    "M45": {"ngc": ["Melotte 22"], "en": ["Pleiades", "Seven Sisters"], "cn": ["昴星团", "七姐妹星团"]},
    "M46": {"ngc": ["NGC 2437"], "en": ["Open Cluster with Planetary Nebula"], "cn": ["船尾座疏散星团"]},
    "M47": {"ngc": ["NGC 2422"], "en": ["Open Cluster in Puppis"], "cn": ["船尾座疏散星团"]},
    "M48": {"ngc": ["NGC 2548"], "en": ["Open Cluster in Hydra"], "cn": ["长蛇座疏散星团"]},
    "M49": {"ngc": ["NGC 4472"], "en": ["Giant Elliptical in Virgo"], "cn": ["室女座椭圆星系"]},
    "M50": {"ngc": ["NGC 2323"], "en": ["Heart-shaped Cluster"], "cn": ["麒麟座疏散星团"]},
    "M51": {"ngc": ["NGC 5194", "NGC 5195"], "en": ["Whirlpool Galaxy", "Question Mark Galaxy"], "cn": ["涡状星系"]},
    "M52": {"ngc": ["NGC 7654"], "en": ["Scorpion Cluster"], "cn": ["仙后座疏散星团"]},
    "M53": {"ngc": ["NGC 5024"], "en": ["Globular Cluster in Coma Berenices"], "cn": ["后发座球状星团"]},
    "M54": {"ngc": ["NGC 6715"], "en": ["Extragalactic Globular Cluster"], "cn": ["人马座球状星团"]},
    "M55": {"ngc": ["NGC 6809"], "en": ["Spectre Globular Cluster"], "cn": ["人马座球状星团"]},
    "M56": {"ngc": ["NGC 6779"], "en": ["Globular Cluster in Lyra"], "cn": ["天琴座球状星团"]},
    "M57": {"ngc": ["NGC 6720"], "en": ["Ring Nebula"], "cn": ["环状星云"]},
    "M58": {"ngc": ["NGC 4579"], "en": ["Barred Spiral in Virgo"], "cn": ["室女座棒旋星系"]},
    "M59": {"ngc": ["NGC 4621"], "en": ["Elliptical Galaxy in Virgo"], "cn": ["室女座椭圆星系"]},
    "M60": {"ngc": ["NGC 4649"], "en": ["Elliptical Galaxy in Virgo Cluster"], "cn": ["室女座椭圆星系"]},
    "M61": {"ngc": ["NGC 4303"], "en": ["Swelling Spiral Galaxy"], "cn": ["室女座旋涡星系"]},
    "M62": {"ngc": ["NGC 6266"], "en": ["Flickering Globular Cluster"], "cn": ["蛇夫座球状星团"]},
    "M63": {"ngc": ["NGC 5055"], "en": ["Sunflower Galaxy"], "cn": ["向日葵星系"]},
    "M64": {"ngc": ["NGC 4826"], "en": ["Black Eye Galaxy", "Sleeping Beauty Galaxy", "Evil Eye Galaxy"], "cn": ["黑眼星系", "睡美人星系"]},
    "M65": {"ngc": ["NGC 3623"], "en": ["Leo Triplet Galaxy"], "cn": ["狮子座旋涡星系", "狮子座三胞胎之一"]},
    "M66": {"ngc": ["NGC 3627"], "en": ["Leo Triplet Galaxy"], "cn": ["狮子座旋涡星系", "狮子座三胞胎之一"]},
    "M67": {"ngc": ["NGC 2682"], "en": ["King Cobra Cluster", "Golden Eye Cluster"], "cn": ["巨蟹座古老疏散星团"]},
    "M68": {"ngc": ["NGC 4590"], "en": ["Globular Cluster in Hydra"], "cn": ["长蛇座球状星团"]},
    "M69": {"ngc": ["NGC 6637"], "en": ["Globular Cluster in Sagittarius"], "cn": ["人马座球状星团"]},
    "M70": {"ngc": ["NGC 6681"], "en": ["Globular Cluster in Sagittarius"], "cn": ["人马座球状星团"]},
    "M71": {"ngc": ["NGC 6838"], "en": ["Angelfish Cluster"], "cn": ["天箭座球状星团"]},
    "M72": {"ngc": ["NGC 6981"], "en": ["Globular Cluster in Aquarius"], "cn": ["宝瓶座球状星团"]},
    "M73": {"ngc": ["NGC 6994"], "en": ["Y-shaped Asterism"], "cn": ["宝瓶座四合星"]},
    "M74": {"ngc": ["NGC 628"], "en": ["Phantom Galaxy", "Grand Design Spiral"], "cn": ["幻影星系"]},
    "M75": {"ngc": ["NGC 6864"], "en": ["Globular Cluster in Sagittarius"], "cn": ["人马座球状星团"]},
    "M76": {"ngc": ["NGC 650", "NGC 651"], "en": ["Little Dumbbell Nebula", "Cork Nebula", "Barbell Nebula"], "cn": ["小哑铃星云"]},
    "M77": {"ngc": ["NGC 1068"], "en": ["Cetus A", "Seyfert Galaxy"], "cn": ["鲸鱼座A", "西佛星系"]},
    "M78": {"ngc": ["NGC 2068"], "en": ["Brightest Reflection Nebula"], "cn": ["猎户座反射星云"]},
    "M79": {"ngc": ["NGC 1904"], "en": ["Globular Cluster in Lepus"], "cn": ["天兔座球状星团"]},
    "M80": {"ngc": ["NGC 6093"], "en": ["Globular Cluster in Scorpius"], "cn": ["天蝎座球状星团"]},
    "M81": {"ngc": ["NGC 3031"], "en": ["Bode's Galaxy"], "cn": ["波德星系"]},
    "M82": {"ngc": ["NGC 3034"], "en": ["Cigar Galaxy", "Starburst Galaxy"], "cn": ["雪茄星系", "星暴星系"]},
    "M83": {"ngc": ["NGC 5236"], "en": ["Southern Pinwheel Galaxy"], "cn": ["南风车星系"]},
    "M84": {"ngc": ["NGC 4374"], "en": ["Lenticular Galaxy in Virgo"], "cn": ["室女座透镜星系"]},
    "M85": {"ngc": ["NGC 4382"], "en": ["Lenticular Galaxy in Coma Berenices"], "cn": ["后发座透镜星系"]},
    "M86": {"ngc": ["NGC 4406"], "en": ["Giant Lenticular in Markarian Chain"], "cn": ["马卡良星系链核心星系"]},
    "M87": {"ngc": ["NGC 4486"], "en": ["Virgo A", "Smoking Gun Galaxy", "Black Hole M87*"], "cn": ["室女A星系", "超大质量黑洞星系"]},
    "M88": {"ngc": ["NGC 4501"], "en": ["Spiral Galaxy in Coma Berenices"], "cn": ["室女座旋涡星系"]},
    "M89": {"ngc": ["NGC 4552"], "en": ["Spherical Galaxy in Virgo"], "cn": ["室女座球状椭圆星系"]},
    "M90": {"ngc": ["NGC 4569"], "en": ["Approaching Spiral Galaxy"], "cn": ["室女座旋涡星系"]},
    "M91": {"ngc": ["NGC 4548"], "en": ["Anemic Barred Spiral"], "cn": ["后发座棒旋星系"]},
    "M92": {"ngc": ["NGC 6341"], "en": ["Northern Globular in Hercules"], "cn": ["武仙座球状星团"]},
    "M93": {"ngc": ["NGC 2447"], "en": ["Butterfly Cluster in Puppis", "Starfish Cluster"], "cn": ["船尾座疏散星团"]},
    "M94": {"ngc": ["NGC 4736"], "en": ["Cat's Eye Galaxy", "Crocodile Eye Galaxy"], "cn": ["猫眼星系", "鳄鱼眼星系"]},
    "M95": {"ngc": ["NGC 3351"], "en": ["Barred Spiral in Leo"], "cn": ["狮子座棒旋星系"]},
    "M96": {"ngc": ["NGC 3368"], "en": ["Double-ring Spiral in Leo"], "cn": ["狮子座双环旋涡星系"]},
    "M97": {"ngc": ["NGC 3587"], "en": ["Owl Nebula"], "cn": ["猫头鹰星云"]},
    "M98": {"ngc": ["NGC 4192"], "en": ["Edge-on Spiral in Coma Berenices"], "cn": ["后发座侧面旋涡星系"]},
    "M99": {"ngc": ["NGC 4254"], "en": ["Coma Pinwheel Galaxy", "Virgo Cluster One-Armed Spiral"], "cn": ["后发座风车星系", "单臂旋涡星系"]},
    "M100": {"ngc": ["NGC 4321"], "en": ["Mirror Galaxy", "Grand Design Spiral in Coma"], "cn": ["后发座对称旋涡星系"]},
    "M101": {"ngc": ["NGC 5457"], "en": ["Pinwheel Galaxy"], "cn": ["风车星系"]},
    "M102": {"ngc": ["NGC 5866"], "en": ["Spindle Galaxy"], "cn": ["纺锤星系"]},
    "M103": {"ngc": ["NGC 581"], "en": ["Christmas Tree Cluster in Cassiopeia"], "cn": ["仙后座疏散星团"]},
    "M104": {"ngc": ["NGC 4594"], "en": ["Sombrero Galaxy"], "cn": ["草帽星系"]},
    "M105": {"ngc": ["NGC 3379"], "en": ["Elliptical Galaxy in Leo"], "cn": ["狮子座椭圆星系"]},
    "M106": {"ngc": ["NGC 4258"], "en": ["Water Maser Galaxy in Canes Venatici"], "cn": ["猎犬座旋涡星系"]},
    "M107": {"ngc": ["NGC 6171"], "en": ["Globular Cluster in Ophiuchus"], "cn": ["蛇夫座球状星团"]},
    "M108": {"ngc": ["NGC 3556"], "en": ["Surfboard Galaxy"], "cn": ["冲浪板星系", "大熊座侧向星系"]},
    "M109": {"ngc": ["NGC 3992"], "en": ["Vacuum Cleaner Galaxy", "Barred Spiral in Ursa Major"], "cn": ["吸尘器星系", "大熊座棒旋星系"]},
    "M110": {"ngc": ["NGC 205"], "en": ["Edward Young Star Cluster Companion", "Andromeda Satellite Galaxy"], "cn": ["仙女座伴星系", "矮椭圆星系"]}
}

# ── 2. All 109 Caldwell Objects ────────────────────────────────────────────
CALDWELL_CATALOG: Dict[str, Dict[str, List[str]]] = {
    "C1": {"ngc": ["NGC 188"], "en": ["Open Cluster in Cepheus"], "cn": ["仙王座疏散星团"]},
    "C2": {"ngc": ["NGC 40"], "en": ["Bow-Tie Nebula"], "cn": ["领结星云"]},
    "C3": {"ngc": ["NGC 4236"], "en": ["Galaxy in Draco"], "cn": ["天龙座棒旋星系"]},
    "C4": {"ngc": ["NGC 7023"], "en": ["Iris Nebula"], "cn": ["鸢尾花星云"]},
    "C5": {"ngc": ["IC 342"], "en": ["Hidden Galaxy"], "cn": ["隐匿星系"]},
    "C6": {"ngc": ["NGC 6543"], "en": ["Cat's Eye Nebula"], "cn": ["猫眼星云"]},
    "C7": {"ngc": ["NGC 2403"], "en": ["Galaxy in Camelopardalis"], "cn": ["鹿豹座旋涡星系"]},
    "C8": {"ngc": ["NGC 559"], "en": ["Open Cluster in Cassiopeia"], "cn": ["仙后座疏散星团"]},
    "C9": {"ngc": ["Sh2-155"], "en": ["Cave Nebula"], "cn": ["洞穴星云"]},
    "C10": {"ngc": ["NGC 663"], "en": ["Open Cluster in Cassiopeia"], "cn": ["仙后座疏散星团"]},
    "C11": {"ngc": ["NGC 7635"], "en": ["Bubble Nebula"], "cn": ["气泡星云"]},
    "C12": {"ngc": ["NGC 6946"], "en": ["Fireworks Galaxy"], "cn": ["烟花星系"]},
    "C13": {"ngc": ["NGC 457"], "en": ["Owl Cluster", "ET Cluster"], "cn": ["猫头鹰星团", "飞人星团"]},
    "C14": {"ngc": ["NGC 869", "NGC 884"], "en": ["Double Cluster in Perseus"], "cn": ["英仙座双星团"]},
    "C15": {"ngc": ["NGC 6826"], "en": ["Blinking Planetary Nebula"], "cn": ["闪烁行星状星云"]},
    "C16": {"ngc": ["NGC 7243"], "en": ["Open Cluster in Lacerta"], "cn": ["蝎虎座疏散星团"]},
    "C17": {"ngc": ["NGC 147"], "en": ["Dwarf Galaxy in Andromeda"], "cn": ["仙女座矮星系"]},
    "C18": {"ngc": ["NGC 185"], "en": ["Dwarf Galaxy in Andromeda"], "cn": ["仙女座矮星系"]},
    "C19": {"ngc": ["IC 5146"], "en": ["Cocoon Nebula"], "cn": ["茧状星云"]},
    "C20": {"ngc": ["NGC 7000"], "en": ["North America Nebula"], "cn": ["北美洲星云"]},
    "C21": {"ngc": ["NGC 4449"], "en": ["Irregular Galaxy in Canes Venatici"], "cn": ["猎犬座不规则星系"]},
    "C22": {"ngc": ["NGC 7662"], "en": ["Blue Snowball Nebula"], "cn": ["蓝色雪球星云"]},
    "C23": {"ngc": ["NGC 891"], "en": ["Silver Sliver Galaxy", "Outer Limits Galaxy"], "cn": ["银币星系"]},
    "C24": {"ngc": ["NGC 1275"], "en": ["Perseus A"], "cn": ["英仙座A"]},
    "C25": {"ngc": ["NGC 2419"], "en": ["Intergalactic Wanderer"], "cn": ["星系际漫游者"]},
    "C26": {"ngc": ["NGC 4244"], "en": ["Silver Needle Galaxy"], "cn": ["银针星系"]},
    "C27": {"ngc": ["NGC 6888"], "en": ["Crescent Nebula"], "cn": ["新月星云", "蛾眉月星云"]},
    "C28": {"ngc": ["NGC 752"], "en": ["Open Cluster in Andromeda"], "cn": ["仙女座疏散星团"]},
    "C29": {"ngc": ["NGC 5005"], "en": ["Spiral Galaxy in Canes Venatici"], "cn": ["猎犬座旋涡星系"]},
    "C30": {"ngc": ["NGC 7331"], "en": ["Deer Lick Galaxy"], "cn": ["鹿角星系", "飞马座旋涡星系"]},
    "C31": {"ngc": ["IC 405"], "en": ["Flaming Star Nebula"], "cn": ["燃烧恒星星云"]},
    "C32": {"ngc": ["NGC 4631"], "en": ["Whale Galaxy"], "cn": ["鲸鱼星系"]},
    "C33": {"ngc": ["NGC 6992", "NGC 6995"], "en": ["Eastern Veil Nebula"], "cn": ["东面纱星云"]},
    "C34": {"ngc": ["NGC 6960"], "en": ["Western Veil Nebula", "Witch's Broom"], "cn": ["西面纱星云", "女巫扫帚星云"]},
    "C35": {"ngc": ["NGC 4889"], "en": ["Coma B"], "cn": ["后发座大椭圆星系"]},
    "C36": {"ngc": ["NGC 4559"], "en": ["Spiral Galaxy in Coma Berenices"], "cn": ["后发座旋涡星系"]},
    "C37": {"ngc": ["NGC 6885"], "en": ["Open Cluster in Vulpecula"], "cn": ["狐狸座疏散星团"]},
    "C38": {"ngc": ["NGC 4565"], "en": ["Needle Galaxy"], "cn": ["针状星系"]},
    "C39": {"ngc": ["NGC 2392"], "en": ["Eskimo Nebula", "Clown Face Nebula"], "cn": ["爱斯基摩星云", "小丑脸星云"]},
    "C40": {"ngc": ["NGC 3626"], "en": ["Lenticular Galaxy in Leo"], "cn": ["狮子座透镜星系"]},
    "C41": {"ngc": ["Melotte 25"], "en": ["Hyades"], "cn": ["毕星团"]},
    "C42": {"ngc": ["NGC 7006"], "en": ["Globular Cluster in Delphinus"], "cn": ["海豚座球状星团"]},
    "C43": {"ngc": ["NGC 7814"], "en": ["Little Sombrero Galaxy"], "cn": ["小草帽星系"]},
    "C44": {"ngc": ["NGC 7479"], "en": ["Superman Galaxy"], "cn": ["超人星系", "飞马座棒旋星系"]},
    "C45": {"ngc": ["NGC 5248"], "en": ["Spiral Galaxy in Bootes"], "cn": ["牧夫座旋涡星系"]},
    "C46": {"ngc": ["NGC 2261"], "en": ["Hubble's Variable Nebula"], "cn": ["哈勃变光星云"]},
    "C47": {"ngc": ["NGC 6934"], "en": ["Globular Cluster in Delphinus"], "cn": ["海豚座球状星团"]},
    "C48": {"ngc": ["NGC 2775"], "en": ["Spiral Galaxy in Cancer"], "cn": ["巨蟹座旋涡星系"]},
    "C49": {"ngc": ["NGC 2237", "NGC 2244"], "en": ["Rosette Nebula"], "cn": ["玫瑰星云"]},
    "C50": {"ngc": ["NGC 2244"], "en": ["Satellite Cluster"], "cn": ["玫瑰星团"]},
    "C51": {"ngc": ["IC 1613"], "en": ["Dwarf Galaxy in Cetus"], "cn": ["鲸鱼座矮不规则星系"]},
    "C52": {"ngc": ["NGC 4697"], "en": ["Elliptical Galaxy in Virgo"], "cn": ["室女座椭圆星系"]},
    "C53": {"ngc": ["NGC 3115"], "en": ["Spindle Galaxy"], "cn": ["纺锤星系"]},
    "C54": {"ngc": ["NGC 2506"], "en": ["Open Cluster in Monoceros"], "cn": ["麒麟座疏散星团"]},
    "C55": {"ngc": ["NGC 7009"], "en": ["Saturn Nebula"], "cn": ["土星状星云"]},
    "C56": {"ngc": ["NGC 246"], "en": ["Skull Nebula"], "cn": ["头骨星云", "骷髅星云"]},
    "C57": {"ngc": ["NGC 6822"], "en": ["Barnard's Galaxy"], "cn": ["巴纳德星系"]},
    "C58": {"ngc": ["NGC 2360"], "en": ["Caroline's Cluster"], "cn": ["卡罗琳星团"]},
    "C59": {"ngc": ["NGC 3242"], "en": ["Ghost of Jupiter"], "cn": ["木星状星云", "木星幽灵"]},
    "C60": {"ngc": ["NGC 4038"], "en": ["Antennae Galaxies"], "cn": ["触须星系", "天线星系"]},
    "C61": {"ngc": ["NGC 4039"], "en": ["Antennae Galaxies Companion"], "cn": ["触须星系伴星系"]},
    "C62": {"ngc": ["NGC 247"], "en": ["Claw Galaxy"], "cn": ["爪状星系"]},
    "C63": {"ngc": ["NGC 7293"], "en": ["Helix Nebula", "Eye of God"], "cn": ["螺旋星云", "上帝之眼"]},
    "C64": {"ngc": ["NGC 2362"], "en": ["Tau Canis Majoris Cluster"], "cn": ["大犬座tau星团", "弓箭手星团"]},
    "C65": {"ngc": ["NGC 253"], "en": ["Sculptor Galaxy", "Silver Coin Galaxy"], "cn": ["玉夫座大星系", "银币星系"]},
    "C66": {"ngc": ["NGC 5694"], "en": ["Globular Cluster in Hydra"], "cn": ["长蛇座球状星团"]},
    "C67": {"ngc": ["NGC 1097"], "en": ["Spiral Galaxy in Fornax"], "cn": ["天炉座棒旋星系"]},
    "C68": {"ngc": ["NGC 6729"], "en": ["R Coronae Australis Nebula"], "cn": ["南冕座变光星云"]},
    "C69": {"ngc": ["NGC 6302"], "en": ["Butterfly Nebula", "Bug Nebula"], "cn": ["蝴蝶星云", "虫状星云"]},
    "C70": {"ngc": ["NGC 300"], "en": ["Southern Pinwheel Galaxy in Sculptor"], "cn": ["玉夫座南风车星系"]},
    "C71": {"ngc": ["NGC 2477"], "en": ["Open Cluster in Puppis"], "cn": ["船尾座疏散星团"]},
    "C72": {"ngc": ["NGC 55"], "en": ["String of Pearls Galaxy"], "cn": ["细绳星系", "玉夫座不规则星系"]},
    "C73": {"ngc": ["NGC 1851"], "en": ["Globular Cluster in Columba"], "cn": ["天鸽座球状星团"]},
    "C74": {"ngc": ["NGC 3132"], "en": ["Southern Ring Nebula", "Eight-Burst Nebula"], "cn": ["南环状星云", "八裂星云"]},
    "C75": {"ngc": ["NGC 6124"], "en": ["Open Cluster in Scorpius"], "cn": ["天蝎座疏散星团"]},
    "C76": {"ngc": ["NGC 6231"], "en": ["False Comet Cluster"], "cn": ["假彗星团"]},
    "C77": {"ngc": ["NGC 5128"], "en": ["Centaurus A"], "cn": ["半人马座A"]},
    "C78": {"ngc": ["NGC 6541"], "en": ["Globular Cluster in Corona Australis"], "cn": ["南冕座球状星团"]},
    "C79": {"ngc": ["NGC 3201"], "en": ["Globular Cluster in Vela"], "cn": ["船帆座球状星团"]},
    "C80": {"ngc": ["NGC 5139"], "en": ["Omega Centauri"], "cn": ["半人马座欧米伽星团"]},
    "C81": {"ngc": ["NGC 6352"], "en": ["Globular Cluster in Ara"], "cn": ["天坛座球状星团"]},
    "C82": {"ngc": ["NGC 6193"], "en": ["Open Cluster in Ara"], "cn": ["天坛座疏散星团"]},
    "C83": {"ngc": ["NGC 4945"], "en": ["Spiral Galaxy in Centaurus"], "cn": ["半人马座棒旋星系"]},
    "C84": {"ngc": ["NGC 5286"], "en": ["Globular Cluster in Centaurus"], "cn": ["半人马座球状星团"]},
    "C85": {"ngc": ["IC 2391"], "en": ["Omicron Velorum Cluster"], "cn": ["船帆座omicron星团"]},
    "C86": {"ngc": ["NGC 6397"], "en": ["Globular Cluster in Ara"], "cn": ["天坛座球状星团"]},
    "C87": {"ngc": ["NGC 1261"], "en": ["Globular Cluster in Horologium"], "cn": ["时钟座球状星团"]},
    "C88": {"ngc": ["NGC 5823"], "en": ["Open Cluster in Circinus"], "cn": ["圆规座疏散星团"]},
    "C89": {"ngc": ["NGC 6087"], "en": ["S Normae Cluster"], "cn": ["矩尺座S星团"]},
    "C90": {"ngc": ["NGC 2867"], "en": ["Planetary Nebula in Carina"], "cn": ["船底座行星状星云"]},
    "C91": {"ngc": ["NGC 3532"], "en": ["Wishing Well Cluster"], "cn": ["许愿井星团"]},
    "C92": {"ngc": ["NGC 3372"], "en": ["Eta Carinae Nebula", "Carina Nebula"], "cn": ["船底座大星云", "海山二星云"]},
    "C93": {"ngc": ["NGC 6752"], "en": ["Great Peacock Globular Cluster"], "cn": ["大孔雀球状星团"]},
    "C94": {"ngc": ["NGC 4755"], "en": ["Jewel Box Cluster", "Kappa Crucis Cluster"], "cn": ["珠宝盒星团"]},
    "C95": {"ngc": ["NGC 6025"], "en": ["Open Cluster in Triangulum Australe"], "cn": ["南三角座疏散星团"]},
    "C96": {"ngc": ["NGC 2516"], "en": ["Southern Pleiades"], "cn": ["南天昴星团"]},
    "C97": {"ngc": ["NGC 3766"], "en": ["Pearl Cluster"], "cn": ["珍珠星团"]},
    "C98": {"ngc": ["NGC 4609"], "en": ["Open Cluster in Crux"], "cn": ["南十字座疏散星团"]},
    "C99": {"ngc": ["Coalsack"], "en": ["Coalsack Nebula"], "cn": ["煤袋星云"]},
    "C100": {"ngc": ["IC 2944"], "en": ["Running Chicken Nebula", "Lambda Centauri Nebula"], "cn": ["奔跑小鸡星云"]},
    "C101": {"ngc": ["NGC 6744"], "en": ["Spiral Galaxy in Pavo"], "cn": ["孔雀座旋涡星系"]},
    "C102": {"ngc": ["IC 2602"], "en": ["Southern Pleiades", "Theta Carinae Cluster"], "cn": ["南七姐妹星团"]},
    "C103": {"ngc": ["NGC 2070"], "en": ["Tarantula Nebula", "30 Doradus"], "cn": ["蜘蛛星云", "狼蛛星云"]},
    "C104": {"ngc": ["NGC 362"], "en": ["Globular Cluster in Tucana"], "cn": ["杜鹃座球状星团"]},
    "C105": {"ngc": ["NGC 4833"], "en": ["Globular Cluster in Musca"], "cn": ["苍蝇座球状星团"]},
    "C106": {"ngc": ["NGC 104"], "en": ["47 Tucanae"], "cn": ["杜鹃座47"]},
    "C107": {"ngc": ["NGC 6101"], "en": ["Globular Cluster in Apus"], "cn": ["天燕座球状星团"]},
    "C108": {"ngc": ["NGC 4372"], "en": ["Globular Cluster in Musca"], "cn": ["苍蝇座球状星团"]},
    "C109": {"ngc": ["NGC 3195"], "en": ["Planetary Nebula in Chamaeleon"], "cn": ["蝘蜓座行星状星云"]}
}

# ── 3. All 88 IAU Constellations ───────────────────────────────────────────
IAU_CONSTELLATIONS: Dict[str, Dict[str, str]] = {
    "And": {"cn": "仙女座", "en": "Andromeda"},
    "Ant": {"cn": "唧筒座", "en": "Antlia"},
    "Aps": {"cn": "天燕座", "en": "Apus"},
    "Aqr": {"cn": "宝瓶座", "en": "Aquarius"},
    "Aql": {"cn": "天鹰座", "en": "Aquila"},
    "Ara": {"cn": "天坛座", "en": "Ara"},
    "Ari": {"cn": "白羊座", "en": "Aries"},
    "Aur": {"cn": "御夫座", "en": "Auriga"},
    "Boo": {"cn": "牧夫座", "en": "Bootes"},
    "Cae": {"cn": "雕具座", "en": "Caelum"},
    "Cam": {"cn": "鹿豹座", "en": "Camelopardalis"},
    "Cnc": {"cn": "巨蟹座", "en": "Cancer"},
    "CVn": {"cn": "猎犬座", "en": "Canes Venatici"},
    "CMa": {"cn": "大犬座", "en": "Canis Major"},
    "CMi": {"cn": "小犬座", "en": "Canis Minor"},
    "Cap": {"cn": "摩羯座", "en": "Capricornus"},
    "Car": {"cn": "船底座", "en": "Carina"},
    "Cas": {"cn": "仙后座", "en": "Cassiopeia"},
    "Cen": {"cn": "半人马座", "en": "Centaurus"},
    "Cep": {"cn": "仙王座", "en": "Cepheus"},
    "Cet": {"cn": "鲸鱼座", "en": "Cetus"},
    "Cha": {"cn": "蝘蜓座", "en": "Chamaeleon"},
    "Cir": {"cn": "圆规座", "en": "Circinus"},
    "Col": {"cn": "天鸽座", "en": "Columba"},
    "Com": {"cn": "后发座", "en": "Coma Berenices"},
    "CrA": {"cn": "南冕座", "en": "Corona Australis"},
    "CrB": {"cn": "北冕座", "en": "Corona Borealis"},
    "Crv": {"cn": "乌鸦座", "en": "Corvus"},
    "Crt": {"cn": "巨爵座", "en": "Crater"},
    "Cru": {"cn": "南十字座", "en": "Crux"},
    "Cyg": {"cn": "天鹅座", "en": "Cygnus"},
    "Del": {"cn": "海豚座", "en": "Delphinus"},
    "Dor": {"cn": "剑鱼座", "en": "Dorado"},
    "Dra": {"cn": "天龙座", "en": "Draco"},
    "Equ": {"cn": "小马座", "en": "Equuleus"},
    "Eri": {"cn": "波江座", "en": "Eridanus"},
    "For": {"cn": "天炉座", "en": "Fornax"},
    "Gem": {"cn": "双子座", "en": "Gemini"},
    "Gru": {"cn": "天鹤座", "en": "Grus"},
    "Her": {"cn": "武仙座", "en": "Hercules"},
    "Hor": {"cn": "时钟座", "en": "Horologium"},
    "Hya": {"cn": "长蛇座", "en": "Hydra"},
    "Hyi": {"cn": "水蛇座", "en": "Hydrus"},
    "Ind": {"cn": "印第安座", "en": "Indus"},
    "Lac": {"cn": "蝎虎座", "en": "Lacerta"},
    "Leo": {"cn": "狮子座", "en": "Leo"},
    "LMi": {"cn": "小狮座", "en": "Leo Minor"},
    "Lep": {"cn": "天兔座", "en": "Lepus"},
    "Lib": {"cn": "天秤座", "en": "Libra"},
    "Lup": {"cn": "豺狼座", "en": "Lupus"},
    "Lyn": {"cn": "天猫座", "en": "Lynx"},
    "Lyr": {"cn": "天琴座", "en": "Lyra"},
    "Men": {"cn": "山案座", "en": "Mensa"},
    "Mic": {"cn": "显微镜座", "en": "Microscopium"},
    "Mon": {"cn": "麒麟座", "en": "Monoceros"},
    "Mus": {"cn": "苍蝇座", "en": "Musca"},
    "Nor": {"cn": "矩尺座", "en": "Norma"},
    "Oct": {"cn": "南极座", "en": "Octans"},
    "Oph": {"cn": "蛇夫座", "en": "Ophiuchus"},
    "Ori": {"cn": "猎户座", "en": "Orion"},
    "Pav": {"cn": "孔雀座", "en": "Pavo"},
    "Peg": {"cn": "飞马座", "en": "Pegasus"},
    "Per": {"cn": "英仙座", "en": "Perseus"},
    "Phe": {"cn": "凤凰座", "en": "Phoenix"},
    "Pic": {"cn": "绘架座", "en": "Pictor"},
    "Psc": {"cn": "双鱼座", "en": "Pisces"},
    "PsA": {"cn": "南鱼座", "en": "Piscis Austrinus"},
    "Pup": {"cn": "船尾座", "en": "Puppis"},
    "Pyx": {"cn": "罗盘座", "en": "Pyxis"},
    "Ret": {"cn": "网罟座", "en": "Reticulum"},
    "Sge": {"cn": "天箭座", "en": "Sagitta"},
    "Sgr": {"cn": "人马座", "en": "Sagittarius"},
    "Sco": {"cn": "天蝎座", "en": "Scorpius"},
    "Scl": {"cn": "玉夫座", "en": "Sculptor"},
    "Sct": {"cn": "盾牌座", "en": "Scutum"},
    "Ser": {"cn": "巨蛇座", "en": "Serpens"},
    "Sex": {"cn": "六分仪座", "en": "Sextans"},
    "Tau": {"cn": "金牛座", "en": "Taurus"},
    "Tel": {"cn": "望远镜座", "en": "Telescopium"},
    "Tri": {"cn": "三角座", "en": "Triangulum"},
    "TrA": {"cn": "南三角座", "en": "Triangulum Australe"},
    "Tuc": {"cn": "杜鹃座", "en": "Tucana"},
    "UMa": {"cn": "大熊座", "en": "Ursa Major"},
    "UMi": {"cn": "小熊座", "en": "Ursa Minor"},
    "Vel": {"cn": "船帆座", "en": "Vela"},
    "Vir": {"cn": "室女座", "en": "Virgo"},
    "Vol": {"cn": "飞鱼座", "en": "Volans"},
    "Vul": {"cn": "狐狸座", "en": "Vulpecula"}
}

# ── 4. Observational Gear & Common Astronomical Equipment ──────────────────
OBSERVING_EQUIPMENT: Dict[str, List[str]] = {
    "UHC": ["Ultra High Contrast", "超高反差滤镜", "UHC滤镜", "[O III]", "H-beta"],
    "OIII": ["O-III", "双重电离氧滤镜", "Oxygen-III", "5007埃", "5000埃"],
    "O-III": ["OIII", "双重电离氧滤镜", "Oxygen-III", "5007埃"],
    "H-BETA": ["H-β", "氢Beta滤镜", "Hydrogen-Beta", "4861埃"],
    "H-ALPHA": ["H-α", "氢Alpha滤镜", "Hydrogen-Alpha", "6563埃"],
    "CLS": ["City Light Suppression", "城市光害滤镜", "宽带光害滤镜"],
    "SCT": ["Schmidt-Cassegrain", "施密特-卡塞格林折反射望远镜", "施卡"],
    "MAK": ["Maksutov-Cassegrain", "马克斯托夫-卡塞格林折反射望远镜", "马卡"],
    "DOB": ["Dobsonian", "道布森望远镜", "杜布森架台"],
}


def build_unified_catalog_map() -> Dict[str, List[str]]:
    """
    Builds a flat cross-catalog alias dictionary for Query Expansion & Entity Routing:
    Maps 'M31' -> ['仙女座大星系', 'Andromeda Galaxy', 'NGC 224', ...]
    """
    unified: Dict[str, List[str]] = {}

    # 1. Messier
    for key, data in MESSIER_CATALOG.items():
        aliases = []
        for cn in data.get("cn", []):
            if cn not in aliases:
                aliases.append(cn)
        for en in data.get("en", []):
            if en not in aliases:
                aliases.append(en)
        for ngc in data.get("ngc", []):
            if ngc not in aliases:
                aliases.append(ngc)
        unified[key] = aliases

        # Also register reverse mappings for primary NGC IDs
        for ngc in data.get("ngc", []):
            if ngc not in unified:
                unified[ngc] = [key] + [a for a in aliases if a != ngc]

    # 2. Caldwell
    for key, data in CALDWELL_CATALOG.items():
        aliases = []
        for ngc in data.get("ngc", []):
            if ngc not in aliases:
                aliases.append(ngc)
        for cn in data.get("cn", []):
            if cn not in aliases:
                aliases.append(cn)
        for en in data.get("en", []):
            if en not in aliases:
                aliases.append(en)
        unified[key] = aliases

        for ngc in data.get("ngc", []):
            if ngc not in unified:
                unified[ngc] = [key] + [a for a in aliases if a != ngc]

    # 3. Constellations
    for code, info in IAU_CONSTELLATIONS.items():
        cn = info["cn"]
        en = info["en"]
        unified[code] = [cn, en]
        if cn not in unified:
            unified[cn] = [en, code]

    # 4. Equipment
    for eq_key, eq_aliases in OBSERVING_EQUIPMENT.items():
        unified[eq_key] = eq_aliases

    return unified


def export_domain_dict_json(target_path: Path = DICT_JSON_PATH):
    """Exports structured domain catalog to domain_dict.json."""
    full_data = {
        "metadata": {
            "version": "1.0.0",
            "messier_count": len(MESSIER_CATALOG),
            "caldwell_count": len(CALDWELL_CATALOG),
            "constellations_count": len(IAU_CONSTELLATIONS),
            "equipment_count": len(OBSERVING_EQUIPMENT),
        },
        "messier": MESSIER_CATALOG,
        "caldwell": CALDWELL_CATALOG,
        "constellations": IAU_CONSTELLATIONS,
        "equipment": OBSERVING_EQUIPMENT,
        "flat_catalog_map": build_unified_catalog_map()
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(full_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Exported domain dictionary to {target_path}")


# Initialize JSON on import if not existing
if not DICT_JSON_PATH.exists():
    export_domain_dict_json(DICT_JSON_PATH)
