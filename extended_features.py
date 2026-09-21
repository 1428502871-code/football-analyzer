# -*- coding: utf-8 -*-
# 扩展特征：赛程密度、旅途疲劳、欧战压制
import numpy as np
from datetime import datetime, timedelta

# 联赛 Tier 基准分（用于欧战跨联赛压制）
LEAGUE_TIER = {
    "英超": 100, "西甲": 98, "德甲": 96, "意甲": 95, "法甲": 92,
    "荷甲": 82, "葡超": 82, "比甲": 78, "苏超": 75, "土超": 78,
    "俄超": 75, "乌超": 72, "希超": 72, "捷甲": 70, "奥甲": 72,
    "瑞超": 68, "挪超": 66, "丹超": 68, "芬超": 62,
    "英冠": 70, "德乙": 68, "西乙": 68, "法乙": 65, "意乙": 65,
    "欧冠": 105, "欧联": 100, "欧协联": 92,
}
DEFAULT_TIER = 55


def calc_schedule_density(team_recent_matches, team_id, match_date_str):
    """返回 (休息天数, 近期赛程强度评分 -1~+1)
    team_recent_matches 是 API 返回的球队近期比赛列表
    match_date_str: 本场比赛日期 YYYY-MM-DD
    """
    try:
        match_date = datetime.strptime(match_date_str, "%Y-%m-%d")
    except Exception:
        return None, 0.0

    # 找出本场之前的所有比赛
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
    last_match = past[0]
    rest_days = (match_date - last_match).days

    # 近 14 天比赛数
    two_weeks_ago = match_date - timedelta(days=14)
    recent_count = sum(1 for d in past if d >= two_weeks_ago)

    # 评分：休息天数 < 3 扣分，> 5 加分；两周 > 5 场扣分
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
    """旅途疲劳系数 -1~+1（正数=客队更累，主队占优）"""
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


def calc_eu_pressure(home_league, away_league, home_elo=None, away_elo=None,
                     w_tier=0.5, w_elo=0.5):
    """欧战跨联赛压制分 -1~+1（正数=主队占优）"""
    h_tier = LEAGUE_TIER.get(home_league, DEFAULT_TIER)
    a_tier = LEAGUE_TIER.get(away_league, DEFAULT_TIER)

    tier_diff = (h_tier - a_tier) / 40.0  # 归一化
    tier_diff = max(-1.0, min(1.0, tier_diff))

    elo_diff = 0.0
    if home_elo is not None and away_elo is not None:
        elo_diff = (home_elo - away_elo) / 200.0
        elo_diff = max(-1.0, min(1.0, elo_diff))

    return round(w_tier * tier_diff + w_elo * elo_diff, 2)


def is_eu_match(league_cn):
    return league_cn in ("欧冠", "欧联", "欧协联")


def is_neutral_league(league_cn):
    """欧战决赛等中立场地（暂未启用）"""
    return False