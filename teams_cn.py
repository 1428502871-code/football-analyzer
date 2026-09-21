# -*- coding: utf-8 -*-
# 中文队名 → 英文队名 映射表
# 说明：以API-Football官方英文名为准，可自行扩充

CN_TEAM_MAP = {
    # ========== 英超 ==========
    "阿森纳": "Arsenal", "切尔西": "Chelsea", "曼城": "Manchester City", "曼彻斯特城": "Manchester City",
    "曼联": "Manchester United", "曼彻斯特联": "Manchester United", "利物浦": "Liverpool",
    "热刺": "Tottenham", "托特纳姆": "Tottenham", "纽卡斯尔": "Newcastle",
    "阿斯顿维拉": "Aston Villa", "布莱顿": "Brighton", "西汉姆": "West Ham",
    "西汉姆联": "West Ham", "埃弗顿": "Everton", "富勒姆": "Fulham",
    "水晶宫": "Crystal Palace", "布伦特福德": "Brentford", "狼队": "Wolves",
    "诺丁汉森林": "Nottingham Forest", "伯恩茅斯": "Bournemouth",
    "莱斯特城": "Leicester", "南安普顿": "Southampton", "伊普斯维奇": "Ipswich",
    # ========== 英冠 ==========
    "利兹联": "Leeds", "伯恩利": "Burnley", "谢菲联": "Sheffield Utd",
    "谢菲尔德联": "Sheffield Utd", "桑德兰": "Sunderland", "米德尔斯堡": "Middlesbrough",
    "西布朗": "West Brom", "诺维奇": "Norwich", "沃特福德": "Watford",
    "考文垂": "Coventry", "布里斯托城": "Bristol City", "斯旺西": "Swansea",
    "卡迪夫城": "Cardiff", "赫尔城": "Hull", "普雷斯顿": "Preston",
    "米尔沃尔": "Millwall", "斯托克城": "Stoke", "布莱克本": "Blackburn",
    "女王公园": "QPR", "牛津联": "Oxford Utd", "德比郡": "Derby",
    "朴茨茅斯": "Portsmouth", "卢顿": "Luton", "普利茅斯": "Plymouth",
    # ========== 西甲 ==========
    "皇马": "Real Madrid", "皇家马德里": "Real Madrid", "巴萨": "Barcelona",
    "巴塞罗那": "Barcelona", "马竞": "Atletico Madrid", "马德里竞技": "Atletico Madrid",
    "塞维利亚": "Sevilla", "毕尔巴鄂": "Athletic Bilbao", "皇家社会": "Real Sociedad",
    "皇家贝蒂斯": "Real Betis", "贝蒂斯": "Real Betis", "比利亚雷亚尔": "Villarreal",
    "瓦伦西亚": "Valencia", "赫罗纳": "Girona", "塞尔塔": "Celta Vigo",
    "拉科鲁尼亚": "Deportivo", "莱万特": "Levante", "西班牙人": "Espanyol",
    "赫塔菲": "Getafe", "巴列卡诺": "Rayo Vallecano", "奥萨苏纳": "Osasuna",
    "马洛卡": "Mallorca", "拉斯帕尔马斯": "Las Palmas", "阿拉维斯": "Alaves",
    # ========== 西乙 ==========
    "莱加内斯": "Leganes", "萨拉戈萨": "Zaragoza", "希洪竞技": "Sporting Gijon",
    "马拉加": "Malaga", "桑坦德": "Racing Santander", "埃瓦尔": "Eibar",
    "韦斯卡": "Huesca", "卡迪斯": "Cadiz", "格拉纳达": "Granada",
    "阿尔梅里亚": "Almeria", "费罗尔": "Ferrol", "米兰德斯": "Mirandes",
    # ========== 德甲 ==========
    "拜仁": "Bayern Munich", "拜仁慕尼黑": "Bayern Munich", "多特": "Dortmund",
    "多特蒙德": "Dortmund", "莱比锡": "RB Leipzig", "勒沃库森": "Bayer Leverkusen",
    "法兰克福": "Eintracht Frankfurt", "斯图加特": "Stuttgart",
    "沃尔夫斯堡": "Wolfsburg", "门兴": "Monchengladbach", "不莱梅": "Werder Bremen",
    "弗赖堡": "Freiburg", "霍芬海姆": "Hoffenheim", "美因茨": "Mainz",
    "奥格斯堡": "Augsburg", "柏林联合": "Union Berlin", "波鸿": "Bochum",
    "海登海姆": "Heidenheim", "圣保利": "St Pauli", "荷尔斯泰因": "Holstein Kiel",
    # ========== 德乙 ==========
    "汉堡": "Hamburger SV", "帕德博恩": "SC Paderborn", "沙尔克": "Schalke",
    "沙尔克04": "Schalke", "杜塞尔多夫": "Fortuna Dusseldorf", "汉诺威": "Hannover",
    "凯泽斯劳滕": "Kaiserslautern", "纽伦堡": "Nurnberg", "卡尔斯鲁厄": "Karlsruher",
    "菲尔特": "Greuther Furth", "柏林赫塔": "Hertha Berlin", "科隆": "Cologne",
    "马格德堡": "Magdeburg", "布伦瑞克": "Braunschweig", "达姆施塔特": "Darmstadt",
    "明斯特": "Preussen Munster", "雷根斯堡": "Regensburg", "乌尔姆": "Ulm",
    # ========== 意甲 ==========
    "尤文": "Juventus", "尤文图斯": "Juventus", "国米": "Inter",
    "国际米兰": "Inter", "AC米兰": "AC Milan", "米兰": "AC Milan",
    "那不勒斯": "Napoli", "罗马": "Roma", "拉齐奥": "Lazio",
    "亚特兰大": "Atalanta", "佛罗伦萨": "Fiorentina", "博洛尼亚": "Bologna",
    "都灵": "Torino", "乌迪内斯": "Udinese", "热那亚": "Genoa",
    "卡利亚里": "Cagliari", "莱切": "Lecce", "维罗纳": "Verona",
    "萨索洛": "Sassuolo", "恩波利": "Empoli", "蒙扎": "Monza", "科莫": "Como",
    "帕尔马": "Parma", "威尼斯": "Venezia",
    # ========== 法甲 ==========
    "巴黎圣日耳曼": "Paris Saint Germain", "巴黎": "Paris Saint Germain",
    "马赛": "Marseille", "里昂": "Lyon", "摩纳哥": "Monaco", "尼斯": "Nice",
    "里尔": "Lille", "朗斯": "Lens", "雷恩": "Rennes", "斯特拉斯堡": "Strasbourg",
    "图卢兹": "Toulouse", "南特": "Nantes", "兰斯": "Reims", "布雷斯特": "Brest",
    "蒙彼利埃": "Montpellier", "勒阿弗尔": "Le Havre", "欧塞尔": "Auxerre",
    "昂热": "Angers", "圣埃蒂安": "Saint-Etienne",
    # ========== 法乙 ==========
    "梅斯": "Metz", "洛里昂": "Lorient", "克莱蒙": "Clermont",
    "阿雅克肖": "Ajaccio", "巴斯蒂亚": "Bastia", "甘冈": "Guingamp",
    "格勒诺布尔": "Grenoble", "罗德兹": "Rodez", "特鲁瓦": "Troyes",
    "亚眠": "Amiens", "波城": "Pau", "拉瓦勒": "Laval",
    # ========== 荷甲 ==========
    "阿贾克斯": "Ajax", "埃因霍温": "PSV Eindhoven", "费耶诺德": "Feyenoord",
    "阿尔克马尔": "AZ Alkmaar", "特温特": "Twente", "乌德勒支": "Utrecht",
    "海伦芬": "Heerenveen", "奈梅亨": "NEC Nijmegen", "鹿特丹斯巴达": "Sparta Rotterdam",
    "格罗宁根": "Groningen", "兹沃勒": "Zwolle", "瓦尔韦克": "Waalwijk",
    "阿尔梅罗": "Almere City", "福图纳": "Fortuna Sittard", "赫拉克勒斯": "Heracles",
    "威廉二世": "Willem II", "布雷达": "NAC Breda",
    # ========== 葡超 ==========
    "波尔图": "Porto", "本菲卡": "Benfica", "里斯本竞技": "Sporting CP",
    "布拉加": "Braga", "吉马良斯": "Vitoria Guimaraes", "博阿维斯塔": "Boavista",
    "法马利康": "Famalicao", "埃斯托里尔": "Estoril", "吉马雷斯": "Vitoria Guimaraes",
    "莫雷伦斯": "Moreirense", "里奥阿维": "Rio Ave", "圣克拉拉": "Santa Clara",
    # ========== 比甲 ==========
    "布鲁日": "Club Brugge", "安德莱赫特": "Anderlecht", "根特": "Gent",
    "亨克": "Genk", "安特卫普": "Antwerp", "标准列日": "Standard Liege",
    "色格拉布鲁日": "Cercle Brugge", "梅赫伦": "Mechelen", "沙勒罗瓦": "Charleroi",
    "科特赖克": "Kortrijk", "圣图尔登": "Sint-Truiden", "奥哈瓦里": "OH Leuven",
    "韦斯特洛": "Westerlo", "登德尔": "Dender",
    # ========== 苏超 ==========
    "凯尔特人": "Celtic", "流浪者": "Rangers", "阿伯丁": "Aberdeen",
    "哈茨": "Hearts", "希伯尼安": "Hibernian", "邓迪联": "Dundee United",
    "圣米伦": "St Mirren", "马瑟韦尔": "Motherwell", "基尔马诺克": "Kilmarnock",
    "罗斯郡": "Ross County", "圣约翰斯通": "St Johnstone", "邓迪": "Dundee",
    # ========== 挪超 ==========
    "博多闪耀": "Bodo/Glimt", "博多格林特": "Bodo/Glimt", "罗森博格": "Rosenborg",
    "莫尔德": "Molde", "布兰": "Brann", "维京": "Viking", "利勒斯特罗姆": "Lillestrom",
    "瓦勒伦加": "Valerenga", "特罗姆瑟": "Tromso", "萨普斯堡": "Sarpsborg 08",
    "斯托姆加斯特": "Strømsgodset", "汉坎": "Ham-Kam", "克里斯蒂安松": "Kristiansund",
    "腓特烈斯塔": "Fredrikstad", "KFUM奥斯陆": "KFUM Oslo", "海于格松": "Haugesund",
    "桑德菲尤尔": "Sandefjord", "奥德": "Odd", "布莱尼": "Bryne",
    # ========== 瑞超 ==========
    "马尔默": "Malmo FF", "佐加顿斯": "Djurgarden", "哈马比": "Hammarby",
    "哥德堡": "Goteborg", "索尔纳": "AIK", "埃尔夫斯堡": "Elfsborg",
    "赫根": "Hacken", "北雪平": "Norrkoping", "卡尔马": "Kalmar FF",
    "米亚尔比": "Mjallby", "代格福什": "Degerfors", "韦纳穆": "Varnamo",
    "天狼星": "Sirius", "布罗马波卡纳": "Brommapojkarna", "哥德堡盖斯": "Gais",
    "哈尔姆斯塔德": "Halmstad", "厄斯特": "Osters",
    # ========== 丹超 ==========
    "哥本哈根": "Copenhagen", "北西兰": "Nordsjaelland", "中日德兰": "Midtjylland",
    "布隆德比": "Brondby", "奥尔堡": "Aalborg", "兰讷斯": "Randers FC",
    "维堡": "Viborg", "锡尔克堡": "Silkeborg", "桑德捷斯基": "Sonderjyske",
    "灵比": "Lyngby", "瓦埃勒": "Vejle", "霍森斯": "Horsens",
    # ========== 芬超 ==========
    "赫尔辛基": "HJK Helsinki", "库奥皮奥": "KuPS", "英特图尔库": "Inter Turku",
    "哈卡": "Haka", "塞伊奈约基": "SJK", "拉赫蒂": "Lahti", "瓦萨": "VPS",
    "玛丽港": "IFK Mariehamn", "伊尔维斯": "Ilves", "洪卡": "Honka",
    # ========== 欧战常见 ==========
    "加拉塔萨雷": "Galatasaray", "费内巴切": "Fenerbahce", "贝西克塔斯": "Besiktas",
    "顿涅茨克矿工": "Shakhtar Donetsk", "基辅迪纳摩": "Dynamo Kyiv",
    "萨尔茨堡": "Salzburg", "年轻人": "Young Boys", "巴塞尔": "Basel",
    "红星": "Red Star Belgrade", "布拉格斯拉维亚": "Slavia Prague",
    "布拉格斯巴达": "Sparta Prague", "比尔森胜利": "Viktoria Plzen",
    "奥林匹亚科斯": "Olympiakos", "帕纳辛纳科斯": "Panathinaikos",
    "雅典AEK": "AEK Athens", "PAOK": "PAOK",
    "里耶卡": "Rijeka", "萨格勒布迪纳摩": "Dinamo Zagreb",
    "卢多戈雷茨": "Ludogorets", "谢里夫": "Sheriff Tiraspol",
    "费伦茨瓦罗斯": "Ferencvaros", "卡拉巴赫": "Qarabag",
    "凯尔特人欧战": "Celtic", "流浪者欧战": "Rangers",
    "特拉维夫马卡比": "Maccabi Tel Aviv", "海法马卡比": "Maccabi Haifa",
    "布拉迪斯拉发": "Slovan Bratislava", "马尔默欧战": "Malmo FF",
    "博多闪耀欧战": "Bodo/Glimt",
}

# 构建反向映射（英文 → 中文）
EN_TO_CN = {}
for cn, en in CN_TEAM_MAP.items():
    if en not in EN_TO_CN:
        EN_TO_CN[en] = cn


def cn_to_en(name):
    """中文转英文"""
    return CN_TEAM_MAP.get(name.strip(), name.strip())


def en_to_cn(en_name):
    """英文转中文，多级降级匹配"""
    if not en_name:
        return en_name
    en_name = en_name.strip()
    # 精确匹配
    if en_name in EN_TO_CN:
        return EN_TO_CN[en_name]
    # 忽略大小写
    el = en_name.lower()
    for en, cn in EN_TO_CN.items():
        if en.lower() == el:
            return cn
    # 去特殊字符后匹配
    cleaned = el.replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
    for en, cn in EN_TO_CN.items():
        ec = en.lower().replace("/", "").replace("-", "").replace(".", "").replace(" ", "")
        if ec == cleaned:
            return cn
    # 模糊包含匹配
    for en, cn in EN_TO_CN.items():
        if en.lower() in el or el in en.lower():
            return cn
    return en_name
    # ============ 伤停原因中文映射 ============
INJURY_REASON_CN = {
    "Hamstring Injury": "腿筋受伤", "Knee Injury": "膝伤", "Ankle Injury": "脚踝伤",
    "Muscle Injury": "肌肉伤", "Thigh Injury": "大腿伤", "Groin Injury": "腹股沟伤",
    "Back Injury": "背伤", "Head Injury": "头部受伤", "Calf Injury": "小腿伤",
    "Hip Injury": "髋部伤", "Knock": "轻伤", "Concussion": "脑震荡",
    "Foot Injury": "脚伤", "Wrist Injury": "手腕伤", "Shoulder Injury": "肩伤",
    "Broken Leg": "腿骨折", "Broken Arm": "手臂骨折", "Fracture": "骨折",
    "Suspended": "停赛", "Yellow Cards": "累积黄牌停赛", "Red Card": "红牌停赛",
    "Illness": "生病", "Virus": "病毒感染", "Cold": "感冒", "Flu": "流感",
    "COVID-19": "新冠", "Personal Reasons": "个人原因", "Rest": "轮休",
    "Injury": "受伤", "Missing Fixture": "缺席本场",
    "Fitness": "体能问题", "Match Fitness": "比赛状态",
    "Torn Ligament": "韧带撕裂", "Strain": "拉伤", "Sprain": "扭伤",
    "Surgery": "手术后恢复",
}


def translate_injury_reason(reason):
    if not reason:
        return "未知"
    if reason in INJURY_REASON_CN:
        return INJURY_REASON_CN[reason]
    rl = reason.lower()
    for en, cn in INJURY_REASON_CN.items():
        if en.lower() in rl:
            return cn
    return reason
