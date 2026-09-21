# -*- coding: utf-8 -*-
import numpy as np
from datetime import datetime, timedelta

LEAGUE_TIER = {
    "英超": 100, "西甲": 98, "德甲": 96, "意甲": 95, "法甲": 92,
    "荷甲": 82, "葡超": 82, "比甲": 78, "苏超": 75, "土超": 78,
    "俄超": 75, "乌超": 72, "希超": 72, "捷甲": 70, "奥甲": 72,
    "瑞超": 68, "挪超": 66, "丹超": 68, "芬超": 62,
    "英冠": 70, "德乙": 68, "西乙": 68, "法乙": 65, "意乙": 65,
    "欧冠": 105, "欧联": 100, "欧协联": 92,
}
DEFAULT_TIER = 55

TEAM_LEAGUE = {
    "Arsenal": "英超", "Chelsea": "英超", "Man City": "英超", "Man United": "英超",
    "Liverpool": "英超", "Tottenham": "英超", "Newcastle": "英超", "Aston Villa": "英超",
    "Real Madrid": "西甲", "Barcelona": "西甲", "Atletico Madrid": "西甲",
    "Athletic Bilbao": "西甲", "Real Sociedad": "西甲", "Girona": "西甲",
    "Bayern Munich": "德甲", "Dortmund": "德甲", "RB Leipzig": "德甲",
    "Bayer Leverkusen": "德甲", "Stuttgart": "德甲", "Eintracht Frankfurt": "德甲",
    "Juventus": "意甲", "Inter": "意甲", "AC Milan": "意甲", "Napoli": "意甲",
    "Roma": "意甲", "Lazio": "意甲", "Atalanta": "意甲", "Bologna": "意甲",
    "Paris Saint Germain": "法甲", "PSG": "法甲", "Monaco": "法甲",
    "Marseille": "法甲", "Lille": "法甲", "Lyon": "法甲", "Nice": "法甲", "Brest": "法甲",
    "Ajax": "荷甲", "PSV Eindhoven": "荷甲", "Feyenoord": "荷甲", "AZ Alkmaar": "荷甲",
    "Porto": "葡超", "Benfica": "葡超", "Sporting CP": "葡超", "Braga": "葡超",
    "Club Brugge": "比甲", "Anderlecht": "比甲", "Gent": "比甲",
    "Celtic": "苏超", "Rangers": "苏超",
    "Salzburg": "奥甲", "Sturm Graz": "奥甲",
    "Young Boys": "瑞超", "Basel": "瑞超", "Servette": "瑞超",
    "Slavia Prague": "捷甲", "Sparta Prague": "捷甲", "Viktoria Plzen": "捷甲",
    "Olympiakos": "希超", "Panathinaikos": "希超", "AEK Athens": "希超", "PAOK": "希超",
    "Galatasaray": "土超", "Fenerbahce": "土超", "Besiktas": "土超",
    "Shakhtar Donetsk": "乌超", "Dynamo Kyiv": "乌超",
    "Red Star Belgrade": "塞超",
    "Dinamo Zagreb": "克甲",
    "Ludogorets": "保甲",
    "Ferencvaros": "匈甲",
    "Qarabag": "阿塞超",
    "Maccabi Tel Aviv": "以超", "Maccabi Haifa": "以超",
    "Slovan Bratislava": "斯洛伐克",
    "Copenhagen": "丹超", "Midtjylland": "丹超", "Nordsjaelland": "丹超",
    "Bodo/Glimt": "挪超", "Molde": "挪超", "Rosenborg": "挪超",
    "Malmo FF": "瑞超", "Djurgarden": "瑞超", "Hammarby": "瑞超",
    "HJK Helsinki": "芬超", "KuPS": "芬超",
}


def calc_schedule_density(team_recent_matches, team_id, match_date_str):
    try:
        match_date = datetime.strptime(match_date_str, "%Y-%m-%d")
    except Exception:
        return None, 0.0

    past = []
    for m in team_recent_matches:
        d = m["fixture"]["date"][:10]
        try:
            d_dt = datetime.strptime(d, "%Y-%m-%d")
        except Exception:
            continue
        if d_dt < match_date:
            past.append(d_dt)
    if not past:
        return None, 0.0

    past.sort(reverse=True)
    rest_days = (match_date - past[0]).days

    two_weeks_ago = match_date - timedelta(days=14)
    recent_count = sum(1 for d in past if d >= two_weeks_ago)

    score = 0.0
    if rest_days <= 2:
        score -= 0.5
    elif rest_days <= 3:
        score -= 0.2
    elif rest_days >= 6:
        score += 0.3

    if recent_count >= 5:
        score -= 0.3
    elif recent_count <= 1:
        score += 0.2

    return rest_days, round(max(-1.0, min(1.0, score)), 2)


def calc_travel_factor(km):
    if km is None:
        return 0.0
    if km < 200:
        return 0.0
    if km < 500:
        return 0.1
    if km < 1000:
        return 0.25
    if km < 2000:
        return 0.4
    if km < 4000:
        return 0.55
    return 0.7


def calc_eu_pressure(home_league, away_league, w_tier=0.5, w_elo=0.5,
                     home_elo=None, away_elo=None):
    h_tier = LEAGUE_TIER.get(home_league, DEFAULT_TIER)
    a_tier = LEAGUE_TIER.get(away_league, DEFAULT_TIER)
    tier_diff = max(-1.0, min(1.0, (h_tier - a_tier) / 40.0))

    elo_diff = 0.0
    if home_elo is not None and away_elo is not None:
        elo_diff = max(-1.0, min(1.0, (home_elo - away_elo) / 200.0))

    return round(w_tier * tier_diff + w_elo * elo_diff, 2)


def get_team_league(team_en_name):
    return TEAM_LEAGUE.get(team_en_name, None)


def is_eu_match(league_cn):
    return league_cn in ("欧冠", "欧联", "欧协联")
