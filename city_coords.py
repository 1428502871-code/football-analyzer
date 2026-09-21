# -*- coding: utf-8 -*-
# 球队所在城市经纬度（用于计算客场旅途距离）

TEAM_CITY = {
    # 英超
    "Arsenal": "London", "Chelsea": "London", "Tottenham": "London",
    "West Ham": "London", "Crystal Palace": "London", "Fulham": "London",
    "Brentford": "London", "Man City": "Manchester", "Man United": "Manchester",
    "Liverpool": "Liverpool", "Everton": "Liverpool",
    "Newcastle": "Newcastle", "Aston Villa": "Birmingham", "Wolves": "Wolverhampton",
    "Brighton": "Brighton", "Nottingham Forest": "Nottingham",
    "Leicester": "Leicester", "Southampton": "Southampton", "Ipswich": "Ipswich",
    "Bournemouth": "Bournemouth",
    # 英冠
    "Leeds": "Leeds", "Burnley": "Burnley", "Sheffield Utd": "Sheffield",
    "Sunderland": "Sunderland", "Middlesbrough": "Middlesbrough",
    "West Brom": "Birmingham", "Norwich": "Norwich", "Watford": "Watford",
    "Coventry": "Coventry", "Bristol City": "Bristol", "Swansea": "Swansea",
    "Cardiff": "Cardiff", "Hull": "Hull", "Preston": "Preston",
    "Millwall": "London", "Stoke": "Stoke", "Blackburn": "Blackburn",
    "QPR": "London", "Oxford Utd": "Oxford", "Derby": "Derby",
    "Portsmouth": "Portsmouth", "Luton": "Luton", "Plymouth": "Plymouth",
    # 西甲
    "Real Madrid": "Madrid", "Atletico Madrid": "Madrid", "Getafe": "Madrid",
    "Rayo Vallecano": "Madrid", "Leganes": "Madrid",
    "Barcelona": "Barcelona", "Espanyol": "Barcelona", "Girona": "Girona",
    "Sevilla": "Sevilla", "Real Betis": "Sevilla",
    "Athletic Bilbao": "Bilbao", "Real Sociedad": "San Sebastian",
    "Villarreal": "Villarreal", "Valencia": "Valencia",
    "Celta Vigo": "Vigo", "Deportivo": "A Coruna", "Levante": "Valencia",
    "Mallorca": "Palma", "Las Palmas": "Las Palmas", "Alaves": "Vitoria",
    "Osasuna": "Pamplona",
    # 德甲
    "Bayern Munich": "Munich", "Dortmund": "Dortmund", "RB Leipzig": "Leipzig",
    "Bayer Leverkusen": "Leverkusen", "Eintracht Frankfurt": "Frankfurt",
    "Stuttgart": "Stuttgart", "Wolfsburg": "Wolfsburg",
    "Monchengladbach": "Monchengladbach", "Werder Bremen": "Bremen",
    "Freiburg": "Freiburg", "Hoffenheim": "Sinsheim", "Mainz": "Mainz",
    "Augsburg": "Augsburg", "Union Berlin": "Berlin", "Bochum": "Bochum",
    "Heidenheim": "Heidenheim", "St Pauli": "Hamburg", "Holstein Kiel": "Kiel",
    "Hamburger SV": "Hamburg", "SC Paderborn": "Paderborn", "Schalke": "Gelsenkirchen",
    "Fortuna Dusseldorf": "Dusseldorf", "Hannover": "Hannover",
    "Hertha Berlin": "Berlin", "Cologne": "Cologne",
    # 意甲
    "Juventus": "Turin", "Torino": "Turin", "Inter": "Milan", "AC Milan": "Milan",
    "Napoli": "Naples", "Roma": "Rome", "Lazio": "Rome",
    "Atalanta": "Bergamo", "Fiorentina": "Florence", "Bologna": "Bologna",
    "Udinese": "Udine", "Genoa": "Genoa", "Cagliari": "Cagliari",
    "Lecce": "Lecce", "Verona": "Verona", "Sassuolo": "Sassuolo",
    "Empoli": "Empoli", "Monza": "Monza", "Como": "Como",
    "Parma": "Parma", "Venezia": "Venice",
    # 法甲
    "Paris Saint Germain": "Paris", "PSG": "Paris", "Marseille": "Marseille",
    "Lyon": "Lyon", "Monaco": "Monaco", "Nice": "Nice", "Lille": "Lille",
    "Lens": "Lens", "Rennes": "Rennes", "Strasbourg": "Strasbourg",
    "Toulouse": "Toulouse", "Nantes": "Nantes", "Reims": "Reims",
    "Brest": "Brest", "Montpellier": "Montpellier", "Le Havre": "Le Havre",
    "Auxerre": "Auxerre", "Angers": "Angers", "Saint-Etienne": "Saint-Etienne",
    # 荷甲
    "Ajax": "Amsterdam", "PSV Eindhoven": "Eindhoven", "Feyenoord": "Rotterdam",
    "AZ Alkmaar": "Alkmaar", "Twente": "Enschede", "Utrecht": "Utrecht",
    # 葡超
    "Porto": "Porto", "Benfica": "Lisbon", "Sporting CP": "Lisbon", "Braga": "Braga",
    # 比甲
    "Club Brugge": "Bruges", "Anderlecht": "Brussels", "Gent": "Ghent",
    # 苏超
    "Celtic": "Glasgow", "Rangers": "Glasgow", "Aberdeen": "Aberdeen",
    "Hearts": "Edinburgh", "Hibernian": "Edinburgh",
    # 北欧
    "Rosenborg": "Trondheim", "Molde": "Molde", "Bodo/Glimt": "Bodo",
    "Brann": "Bergen", "Viking": "Stavanger", "Lillestrom": "Lillestrom",
    "Malmo FF": "Malmo", "Djurgarden": "Stockholm", "Hammarby": "Stockholm",
    "Goteborg": "Gothenburg", "AIK": "Stockholm",
    "Copenhagen": "Copenhagen", "Nordsjaelland": "Farum", "Midtjylland": "Herning",
    "Brondby": "Brondby", "Aalborg": "Aalborg",
    "HJK Helsinki": "Helsinki", "KuPS": "Kuopio",
    # 欧战常见
    "Galatasaray": "Istanbul", "Fenerbahce": "Istanbul", "Besiktas": "Istanbul",
    "Shakhtar Donetsk": "Donetsk", "Dynamo Kyiv": "Kyiv",
    "Salzburg": "Salzburg", "Young Boys": "Bern", "Basel": "Basel",
    "Red Star Belgrade": "Belgrade", "Slavia Prague": "Prague",
    "Sparta Prague": "Prague", "Olympiakos": "Athens",
    "Panathinaikos": "Athens", "AEK Athens": "Athens", "PAOK": "Thessaloniki",
    "Dinamo Zagreb": "Zagreb", "Ludogorets": "Razgrad",
    "Ferencvaros": "Budapest", "Qarabag": "Baku",
    "Maccabi Tel Aviv": "Tel Aviv", "Maccabi Haifa": "Haifa",
    "Slovan Bratislava": "Bratislava",
}

CITY_COORDS = {
    "London": (51.5074, -0.1278), "Manchester": (53.4808, -2.2426),
    "Liverpool": (53.4084, -2.9916), "Newcastle": (54.9783, -1.6178),
    "Birmingham": (52.4862, -1.8904), "Wolverhampton": (52.5869, -2.1288),
    "Brighton": (50.8225, -0.1372), "Nottingham": (52.9548, -1.1581),
    "Leicester": (52.6369, -1.1398), "Southampton": (50.9097, -1.4044),
    "Ipswich": (52.0567, 1.1482), "Bournemouth": (50.7192, -1.8808),
    "Leeds": (53.8008, -1.5491), "Burnley": (53.7892, -2.2484),
    "Sheffield": (53.3811, -1.4701), "Sunderland": (54.9069, -1.3838),
    "Middlesbrough": (54.5742, -1.2350), "Norwich": (52.6309, 1.2974),
    "Watford": (51.6565, -0.3903), "Coventry": (52.4068, -1.5197),
    "Bristol": (51.4545, -2.5879), "Swansea": (51.6214, -3.9436),
    "Cardiff": (51.4816, -3.1791), "Hull": (53.7676, -0.3274),
    "Preston": (53.7632, -2.7031), "Stoke": (53.0027, -2.1794),
    "Blackburn": (53.7484, -2.4820), "Oxford": (51.7520, -1.2577),
    "Derby": (52.9221, -1.4748), "Portsmouth": (50.8198, -1.0874),
    "Luton": (51.8787, -0.4200), "Plymouth": (50.3755, -4.1427),
    "Madrid": (40.4168, -3.7038), "Barcelona": (41.3851, 2.1734),
    "Girona": (41.9794, 2.8214), "Sevilla": (37.3891, -5.9845),
    "Bilbao": (43.2630, -2.9350), "San Sebastian": (43.3183, -1.9812),
    "Villarreal": (39.9380, -0.1014), "Valencia": (39.4699, -0.3763),
    "Vigo": (42.2406, -8.7207), "A Coruna": (43.3623, -8.4115),
    "Palma": (39.5696, 2.6502), "Las Palmas": (28.1235, -15.4365),
    "Vitoria": (42.8467, -2.6716), "Pamplona": (42.8125, -1.6458),
    "Munich": (48.1351, 11.5820), "Dortmund": (51.5136, 7.4653),
    "Leipzig": (51.3397, 12.3731), "Leverkusen": (51.0459, 7.0192),
    "Frankfurt": (50.1109, 8.6821), "Stuttgart": (48.7758, 9.1829),
    "Wolfsburg": (52.4227, 10.7865), "Monchengladbach": (51.1805, 6.4428),
    "Bremen": (53.0793, 8.8017), "Freiburg": (47.9990, 7.8421),
    "Sinsheim": (49.2522, 8.8799), "Mainz": (49.9929, 8.2473),
    "Augsburg": (48.3705, 10.8978), "Berlin": (52.5200, 13.4050),
    "Bochum": (51.4818, 7.2162), "Heidenheim": (48.6768, 10.1545),
    "Hamburg": (53.5511, 9.9937), "Kiel": (54.3233, 10.1228),
    "Paderborn": (51.7189, 8.7575), "Gelsenkirchen": (51.5177, 7.0862),
    "Dusseldorf": (51.2277, 6.7735), "Hannover": (52.3759, 9.7320),
    "Cologne": (50.9375, 6.9603),
    "Turin": (45.0703, 7.6869), "Milan": (45.4642, 9.1900),
    "Naples": (40.8518, 14.2681), "Rome": (41.9028, 12.4964),
    "Bergamo": (45.6983, 9.6773), "Florence": (43.7696, 11.2558),
    "Bologna": (44.4949, 11.3426), "Udine": (46.0711, 13.2346),
    "Genoa": (44.4056, 8.9463), "Cagliari": (39.2238, 9.1217),
    "Lecce": (40.3515, 18.1750), "Verona": (45.4384, 10.9916),
    "Sassuolo": (44.5405, 10.7846), "Empoli": (43.7177, 10.9450),
    "Monza": (45.5845, 9.2744), "Como": (45.8081, 9.0852),
    "Parma": (44.8015, 10.3279), "Venice": (45.4408, 12.3155),
    "Paris": (48.8566, 2.3522), "Marseille": (43.2965, 5.3698),
    "Lyon": (45.7640, 4.8357), "Monaco": (43.7384, 7.4246),
    "Nice": (43.7102, 7.2620), "Lille": (50.6292, 3.0573),
    "Lens": (50.4337, 2.8268), "Rennes": (48.1173, -1.6778),
    "Strasbourg": (48.5734, 7.7521), "Toulouse": (43.6047, 1.4442),
    "Nantes": (47.2184, -1.5536), "Reims": (49.2583, 4.0317),
    "Brest": (48.3904, -4.4861), "Montpellier": (43.6108, 3.8767),
    "Le Havre": (49.4944, 0.1079), "Auxerre": (47.7982, 3.5675),
    "Angers": (47.4784, -0.5632), "Saint-Etienne": (45.4397, 4.3872),
    "Amsterdam": (52.3676, 4.9041), "Eindhoven": (51.4416, 5.4697),
    "Rotterdam": (51.9244, 4.4777), "Alkmaar": (52.6324, 4.7534),
    "Enschede": (52.2215, 6.8937), "Utrecht": (52.0907, 5.1214),
    "Porto": (41.1579, -8.6291), "Lisbon": (38.7223, -9.1393),
    "Braga": (41.5454, -8.4265),
    "Bruges": (51.2093, 3.2247), "Brussels": (50.8503, 4.3517),
    "Ghent": (51.0543, 3.7174),
    "Glasgow": (55.8642, -4.2518), "Aberdeen": (57.1497, -2.0943),
    "Edinburgh": (55.9533, -3.1883),
    "Trondheim": (63.4305, 10.3951), "Molde": (62.7372, 7.1607),
    "Bodo": (67.2804, 14.4049), "Bergen": (60.3913, 5.3221),
    "Stavanger": (58.9700, 5.7331), "Lillestrom": (59.9555, 11.0496),
    "Malmo": (55.6050, 13.0038), "Stockholm": (59.3293, 18.0686),
    "Gothenburg": (57.7089, 11.9746),
    "Copenhagen": (55.6761, 12.5683), "Farum": (55.8083, 12.3550),
    "Herning": (56.1395, 8.9736), "Brondby": (55.6500, 12.4167),
    "Aalborg": (57.0488, 9.9217),
    "Helsinki": (60.1699, 24.9384), "Kuopio": (62.8924, 27.6770),
    "Istanbul": (41.0082, 28.9784), "Donetsk": (48.0159, 37.8028),
    "Kyiv": (50.4501, 30.5234), "Salzburg": (47.8095, 13.0550),
    "Bern": (46.9480, 7.4474), "Basel": (47.5596, 7.5886),
    "Belgrade": (44.7866, 20.4489), "Prague": (50.0755, 14.4378),
    "Athens": (37.9838, 23.7275), "Thessaloniki": (40.6401, 22.9444),
    "Zagreb": (45.8150, 15.9819), "Razgrad": (43.5344, 26.5214),
    "Budapest": (47.4979, 19.0402), "Baku": (40.4093, 49.8671),
    "Tel Aviv": (32.0853, 34.7818), "Haifa": (32.7940, 34.9896),
    "Bratislava": (48.1486, 17.1077),
}


def haversine(lat1, lon1, lat2, lon2):
    """两点间距离，单位公里"""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def get_travel_km(home_team_en, away_team_en):
    """计算两队之间大圆距离（公里），数据缺失返回 None"""
    try:
        h_city = TEAM_CITY.get(home_team_en)
        a_city = TEAM_CITY.get(away_team_en)
        if not h_city or not a_city:
            return None
        h_coord = CITY_COORDS.get(h_city)
        a_coord = CITY_COORDS.get(a_city)
        if not h_coord or not a_coord:
            return None
        return round(haversine(h_coord[0], h_coord[1], a_coord[0], a_coord[1]), 0)
    except Exception:
        return None