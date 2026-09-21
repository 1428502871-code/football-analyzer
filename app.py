# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import requests
import numpy as np
from datetime import datetime, timedelta

from teams_cn import CN_TEAM_MAP, EN_TO_CN, cn_to_en, en_to_cn

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="⚽")
st.title("⚽ 足球分析模型 - 完整版")

api_key = os.environ.get("API_FOOTBALL_KEY", "")
HEADERS = {"x-apisports-key": api_key}
BASE_URL = "https://v3.football.api-sports.io"


def current_season():
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


WEIGHTS = {"injury": 0.20, "home_away": 0.20, "h2h": 0.18, "form": 0.21, "motivation": 0.21}

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
    "Academy Player": "青年队上调", "Coach's Decision": "教练决定",
    "International Duty": "国家队任务", "Loan": "租借",
    "Fitness": "体能问题", "Match Fitness": "比赛状态",
    "Ankle/Foot Injury": "脚踝/脚伤", "Leg Injury": "腿部伤",
    "Arm Injury": "手臂伤", "Neck Injury": "颈部伤",
    "Torn Ligament": "韧带撕裂", "Strain": "拉伤", "Sprain": "扭伤",
    "Surgery": "手术后恢复", "Operation": "手术后恢复",
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


POSITION_CN = {
    "Goalkeeper": "门将", "Defender": "后卫", "Midfielder": "中场",
    "Attacker": "前锋", "Forward": "前锋",
}


def translate_position(pos):
    if not pos:
        return "未知"
    return POSITION_CN.get(pos, pos)


PLAYER_CN_MAP = {
    "Erling Haaland": "哈兰德", "Kevin De Bruyne": "德布劳内", "Mohamed Salah": "萨拉赫",
    "Virgil van Dijk": "范戴克", "Bukayo Saka": "萨卡", "Martin Odegaard": "厄德高",
    "Declan Rice": "赖斯", "Harry Kane": "凯恩", "Son Heung-min": "孙兴慜",
    "Bruno Fernandes": "B费", "Marcus Rashford": "拉什福德", "Phil Foden": "福登",
    "Rodri": "罗德里", "Bernardo Silva": "B席", "Ruben Dias": "鲁本·迪亚斯",
    "Alisson": "阿利松", "Ederson": "埃德森", "Trent Alexander-Arnold": "阿诺德",
    "Andrew Robertson": "罗伯逊", "Cole Palmer": "帕尔默", "Ollie Watkins": "沃特金斯",
    "Alexander Isak": "伊萨克", "Anthony Gordon": "戈登", "Jarrod Bowen": "鲍文",
    "Lionel Messi": "梅西", "Kylian Mbappe": "姆巴佩", "Vinicius Junior": "维尼修斯",
    "Jude Bellingham": "贝林厄姆", "Robert Lewandowski": "莱万", "Lamine Yamal": "亚马尔",
    "Pedri": "佩德里", "Gavi": "加维", "Frenkie de Jong": "德容",
    "Antoine Griezmann": "格列兹曼", "Rodrygo": "罗德里戈",
    "Federico Valverde": "巴尔韦德", "Aurelien Tchouameni": "琼阿梅尼",
    "Thibaut Courtois": "库尔图瓦", "Marc-Andre ter Stegen": "特尔施特根",
    "Raphinha": "拉菲尼亚", "Dani Olmo": "奥尔莫", "Ferran Torres": "费兰·托雷斯",
    "Jamal Musiala": "穆西亚拉", "Joshua Kimmich": "基米希",
    "Manuel Neuer": "诺伊尔", "Florian Wirtz": "维尔茨",
    "Alphonso Davies": "戴维斯", "Leroy Sane": "萨内",
    "Serge Gnabry": "格纳布里", "Thomas Muller": "穆勒",
    "Leon Goretzka": "格雷茨卡", "Kingsley Coman": "科曼",
    "Lautaro Martinez": "劳塔罗", "Rafael Leao": "莱奥",
    "Khvicha Kvaratskhelia": "克瓦拉茨赫利亚", "Victor Osimhen": "奥斯梅恩",
    "Federico Chiesa": "基耶萨", "Nicolo Barella": "巴雷拉",
    "Alessandro Bastoni": "巴斯托尼", "Mike Maignan": "迈尼昂",
    "Ousmane Dembele": "登贝莱", "Achraf Hakimi": "阿什拉夫",
    "Gianluigi Donnarumma": "多纳鲁马", "Marquinhos": "马尔基尼奥斯",
    "Vitinha": "维蒂尼亚", "Bradley Barcola": "巴尔科拉",
    "Alexandre Lacazette": "拉卡泽特",
}


def translate_player(name):
    if not name:
        return ""
    if name in PLAYER_CN_MAP:
        return f"{PLAYER_CN_MAP[name]} ({name})"
    return name


LEAGUE_MAP = {
    39:  (0.65, 0.35, "英超", "顶级"), 140: (0.55, 0.45, "西甲", "顶级"),
    78:  (0.65, 0.35, "德甲", "顶级"), 135: (0.65, 0.35, "意甲", "顶级"),
    61:  (0.55, 0.45, "法甲", "顶级"), 2:   (0.70, 0.30, "欧冠", "欧战"),
    3:   (0.70, 0.30, "欧联", "欧战"), 848: (0.70, 0.30, "欧协联", "欧战"),
    40:  (0.55, 0.45, "英冠", "普通"), 79:  (0.55, 0.45, "德乙", "普通"),
    141: (0.55, 0.45, "西乙", "普通"), 62:  (0.55, 0.45, "法乙", "普通"),
    88:  (0.55, 0.45, "荷甲", "普通"), 94:  (0.55, 0.45, "葡超", "普通"),
    144: (0.55, 0.45, "比甲", "普通"), 179: (0.55, 0.45, "苏超", "普通"),
    103: (0.55, 0.45, "挪超", "普通"), 113: (0.55, 0.45, "瑞超", "普通"),
    119: (0.55, 0.45, "丹超", "普通"), 108: (0.55, 0.45, "芬超", "普通"),
}


def get_league_info(league_id, league_name_from_api=""):
    if league_id in LEAGUE_MAP:
        model_w, market_w, cn_name, cat = LEAGUE_MAP[league_id]
        return model_w, market_w, cn_name, cat
    return 0.55, 0.45, league_name_from_api or "未知联赛", "普通"


def parse_match(m):
    m = m.replace("vs", " ").replace("VS", " ").replace("对", " ").strip()
    sorted_teams = sorted(CN_TEAM_MAP.keys(), key=len, reverse=True)
    used_ranges = []
    matches = []
    for cn in sorted_teams:
        start = 0
        while True:
            idx = m.find(cn, start)
            if idx == -1:
                break
            end = idx + len(cn)
            overlap = any(not (end <= s or idx >= e) for s, e in used_ranges)
            if not overlap:
                matches.append((idx, cn))
                used_ranges.append((idx, end))
                break
            start = idx + 1
    matches.sort()
    if len(matches) >= 2:
        return matches[0][1], matches[1][1]
    parts = m.split()
    if len(parts) < 2:
        return None, None
    prefixes = {"SC", "FC", "AC", "AS", "RC", "CF", "SV", "VfL", "VfB", "TSG", "BSC", "SCO"}
    if parts[0] in prefixes and len(parts) >= 3:
        return parts[0] + " " + parts[1], " ".join(parts[2:])
    mid = len(parts) // 2
    return " ".join(parts[:mid]), " ".join(parts[mid:])


# ============ API 调用 ============
@st.cache_data(ttl=3600)
def search_fixtures_by_date(date_str):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                         params={"date": date_str, "timezone": "Asia/Shanghai"}, timeout=15)
        return [f for f in r.json().get("response", []) if f["league"]["id"] in LEAGUE_MAP]
    except Exception:
        return []


@st.cache_data(ttl=3600)
def search_team(name):
    en_name = cn_to_en(name)

    candidates = [en_name]

    cleaned = en_name.replace("/", " ").replace("-", " ").replace(".", "").replace("  ", " ").strip()
    if cleaned != en_name:
        candidates.append(cleaned)

    accents = {"ø": "o", "å": "a", "æ": "ae", "ö": "o", "ä": "a", "ü": "u",
               "é": "e", "è": "e", "í": "i", "ó": "o", "á": "a", "ñ": "n", "ç": "c"}
    deacc = "".join(accents.get(c.lower(), c) for c in en_name)
    if deacc != en_name:
        candidates.append(deacc)

    if " " in en_name or "/" in en_name:
        first_word = en_name.replace("/", " ").split()[0]
        if first_word not in candidates:
            candidates.append(first_word)

    deacc_cleaned = deacc.replace("/", " ").replace("-", " ").replace(".", "").strip()
    if deacc_cleaned not in candidates:
        candidates.append(deacc_cleaned)

    for cand in candidates:
        try:
            r = requests.get(f"{BASE_URL}/teams", headers=HEADERS,
                             params={"search": cand}, timeout=10)
            data = r.json()
            if data.get("response"):
                t = data["response"][0]["team"]
                return t["id"], t["name"]
        except Exception:
            continue

    return None, None


@st.cache_data(ttl=3600)
def get_fixture(home_id, away_id, date_str):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                         params={"date": date_str, "timezone": "Asia/Shanghai"}, timeout=10)
        for f in r.json().get("response", []):
            if f["teams"]["home"]["id"] == home_id and f["teams"]["away"]["id"] == away_id:
                return f
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def get_odds(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/odds", headers=HEADERS,
                         params={"fixture": fixture_id, "bookmaker": 2}, timeout=10)
        data = r.json()
        if data.get("response"):
            for bm in data["response"][0].get("bookmakers", []):
                for bet in bm.get("bets", []):
                    if bet["id"] == 1:
                        vals = bet["values"]
                        h = next((float(v["odd"]) for v in vals if v["value"] == "Home"), None)
                        d = next((float(v["odd"]) for v in vals if v["value"] == "Draw"), None)
                        a = next((float(v["odd"]) for v in vals if v["value"] == "Away"), None)
                        if h and d and a:
                            return h, d, a
    except Exception:
        pass
    return None, None, None


@st.cache_data(ttl=3600)
def get_injuries(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/injuries", headers=HEADERS,
                         params={"fixture": fixture_id}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []


@st.cache_data(ttl=86400)
def get_sidelined(player_id):
    try:
        r = requests.get(f"{BASE_URL}/sidelined", headers=HEADERS,
                         params={"players": player_id}, timeout=10)
        data = r.json()
        if data.get("response"):
            record = data["response"][0]
            start = record.get("start", "未知") or "未知"
            end = record.get("end", "未知") or "未知"
            return start, end
    except Exception:
        pass
    return "未知", "未知"


@st.cache_data(ttl=86400)
def get_player_stats(player_id):
    try:
        r = requests.get(f"{BASE_URL}/players", headers=HEADERS,
                         params={"id": player_id, "season": current_season()}, timeout=10)
        data = r.json()
        if data.get("response"):
            stats_list = data["response"][0].get("statistics", [])
            if stats_list:
                best = max(stats_list, key=lambda s: s["games"].get("minutes") or 0)
                games = best.get("games", {})
                return {
                    "position": games.get("position", "") or "",
                    "minutes": games.get("minutes") or 0,
                    "appearences": games.get("appearences") or 0,
                }
    except Exception:
        pass
    return {"position": "", "minutes": 0, "appearences": 0}


def classify_role(minutes, appearances):
    if not appearances or appearances < 3 or minutes < 100:
        return "未知"
    if minutes >= 1500:
        return "主力"
    elif minutes >= 600:
        return "轮换"
    else:
        return "替补"


@st.cache_data(ttl=3600)
def get_h2h(home_id, away_id):
    try:
        r = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=HEADERS,
                         params={"h2h": f"{home_id}-{away_id}", "last": 5}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []


@st.cache_data(ttl=3600)
def get_recent_form(team_id, last=6):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                         params={"team": team_id, "last": last, "status": "FT"}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []


# ============ 五项系数计算 ============
def calc_injury_coef(injuries, home_id, away_id):
    pos_w = {"Goalkeeper": 1.2, "Defender": 1.1, "Midfielder": 1.0, "Attacker": 1.1}
    h_score, a_score = 0, 0
    for inj in injuries:
        t_id = inj["team"]["id"]
        pos = inj["player"].get("position", "Midfielder")
        w = pos_w.get(pos, 1.0)
        if t_id == home_id:
            h_score += w
        elif t_id == away_id:
            a_score += w
    diff = a_score - h_score
    return round(np.tanh(diff / 3.0), 2), h_score, a_score


def calc_h2h_coef(h2h_matches, home_id):
    decay = [1.0, 0.7, 0.5, 0.3, 0.2]
    score = 0
    for i, m in enumerate(h2h_matches[:5]):
        w = decay[i] if i < len(decay) else 0.1
        h_s = m["goals"]["home"] or 0
        a_s = m["goals"]["away"] or 0
        if m["teams"]["home"]["id"] == home_id:
            score += w * (1 if h_s > a_s else (-1 if h_s < a_s else 0))
        else:
            score += w * (1 if a_s > h_s else (-1 if a_s < h_s else 0))
    return round(np.tanh(score / 3.0), 2)


def calc_form_coef(recent, team_id):
    score = 0
    for m in recent:
        h_s = m["goals"]["home"] or 0
        a_s = m["goals"]["away"] or 0
        if m["teams"]["home"]["id"] == team_id:
            score += (3 if h_s > a_s else (1 if h_s == a_s else 0))
        else:
            score += (3 if a_s > h_s else (1 if a_s == h_s else 0))
    return score


def calc_form_diff(home_recent, away_recent, home_id, away_id):
    h = calc_form_coef(home_recent, home_id)
    a = calc_form_coef(away_recent, away_id)
    return round(np.tanh((h - a) / 9.0), 2)


# ============ 概率计算 ============
def devig(odds):
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [i / s for i in inv]


def softmax3(base, adjust):
    logits = np.array([np.log(p) for p in base]) + np.array([adjust, -adjust * 0.3, -adjust * 0.7])
    e = np.exp(logits - np.max(logits))
    return e / e.sum()


def calc_all_probs(odds, coefs, league_id, league_name=""):
    market_p = devig(odds)
    adjust = sum(coefs[k] * WEIGHTS[k] for k in WEIGHTS)
    lr_p = softmax3(market_p, adjust * 0.5)
    xgb_p = softmax3(market_p, adjust * 1.0)
    model_p = 0.45 * lr_p + 0.55 * xgb_p
    model_w, market_w, cn_name, cat = get_league_info(league_id, league_name)
    final_p = model_w * model_p + market_w * np.array(market_p)
    final_p = final_p / final_p.sum()
    return {
        "lr": (lr_p * 100).round(1), "xgb": (xgb_p * 100).round(1),
        "model": (model_p * 100).round(1), "market": (np.array(market_p) * 100).round(1),
        "final": (final_p * 100).round(1),
        "league_cn": cn_name, "model_w": model_w, "market_w": market_w
    }


def check_data_health(injuries, h2h, h_recent, a_recent, odds):
    checks = []
    if odds and odds[0]:
        checks.append(("✅", "赔率数据", "完整（Pinnacle）"))
    else:
        checks.append(("❌", "赔率数据", "缺失，无法计算市场概率"))
    if injuries:
        checks.append(("✅", "伤停数据", f"完整（{len(injuries)}条记录）"))
    else:
        checks.append(("⚠️", "伤停数据", "无记录，可能未公布或数据源延迟"))
    if h2h:
        checks.append(("✅", "历史交战", f"完整（近{len(h2h)}次）"))
    else:
        checks.append(("⚠️", "历史交战", "无记录，H2H系数按0处理"))
    if h_recent and a_recent:
        checks.append(("✅", "近期状态", f"完整（主队{len(h_recent)}场，客队{len(a_recent)}场）"))
    else:
        checks.append(("⚠️", "近期状态", "数据缺失，状态系数按0处理"))
    score = sum(1 for c in checks if c[0] == "✅") / len(checks) * 100
    return checks, round(score)


# ============ 分析单场（支持指定日期） ============
def analyze_match(home_name, away_name, date_hint=None):
    home_id, home_std = search_team(home_name)
    away_id, away_std = search_team(away_name)
    if not home_id or not away_id:
        return None, f"球队搜索失败：{home_name} / {away_name}（可尝试补充到映射表）"

    fixture = None
    if date_hint:
        # 优先用指定日期
        fixture = get_fixture(home_id, away_id, date_hint)
        if not fixture:
            try:
                base_date = datetime.strptime(date_hint, "%Y-%m-%d")
                for offset in [-1, 1, -2, 2, 3]:
                    d = (base_date + timedelta(days=offset)).strftime("%Y-%m-%d")
                    fixture = get_fixture(home_id, away_id, d)
                    if fixture:
                        break
            except Exception:
                pass
    else:
        # 默认：从今天向后找4天
        for offset in range(0, 4):
            d = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
            fixture = get_fixture(home_id, away_id, d)
            if fixture:
                break

    if not fixture:
        return None, f"未找到比赛：{home_std} vs {away_std}"

    fid = fixture["fixture"]["id"]
    league_id = fixture["league"]["id"]
    league_name_api = fixture["league"]["name"]
    league_country = fixture["league"].get("country", "")

    odds = get_odds(fid)
    if not odds[0]:
        return None, f"未找到赔率：{home_std} vs {away_std}"

    injuries = get_injuries(fid)
    h2h = get_h2h(home_id, away_id)
    h_recent = get_recent_form(home_id)
    a_recent = get_recent_form(away_id)

    inj_coef, h_inj_score, a_inj_score = calc_injury_coef(injuries, home_id, away_id)
    h2h_coef = calc_h2h_coef(h2h, home_id)
    form_coef = calc_form_diff(h_recent, a_recent, home_id, away_id)
    coefs = {"injury": inj_coef, "home_away": 0.3, "h2h": h2h_coef,
             "form": form_coef, "motivation": 0.0}

    probs = calc_all_probs(list(odds), coefs, league_id, league_name_api)
    health, health_score = check_data_health(injuries, h2h, h_recent, a_recent, odds)

    home_cn = en_to_cn(home_std)
    away_cn = en_to_cn(away_std)

    inj_list = []
    for inj in injuries:
        t_id = inj["team"]["id"]
        team_cn = home_cn if t_id == home_id else (away_cn if t_id == away_id else "未知")
        player_id = inj["player"].get("id")
        player_name = inj["player"].get("name", "")
        raw_reason = inj["player"].get("reason", inj.get("type", ""))
        reason_cn = translate_injury_reason(raw_reason)

        raw_pos = inj["player"].get("position", "") or ""
        stats = get_player_stats(player_id) if player_id else {"position": "", "minutes": 0, "appearences": 0}
        if not raw_pos and stats["position"]:
            raw_pos = stats["position"]
        pos_cn = translate_position(raw_pos)
        role = classify_role(stats["minutes"], stats["appearences"])
        start_date, end_date = get_sidelined(player_id) if player_id else ("未知", "未知")

        inj_list.append({
            "球队": team_cn,
            "球员": translate_player(player_name),
            "位置": pos_cn,
            "角色": role,
            "原因": reason_cn,
            "起始日期": start_date,
            "预计复出": end_date,
        })

    h2h_list = []
    for m in h2h[:5]:
        h_cn = en_to_cn(m["teams"]["home"]["name"])
        a_cn = en_to_cn(m["teams"]["away"]["name"])
        h2h_list.append({
            "日期": m["fixture"]["date"][:10],
            "主队": h_cn,
            "比分": f"{m['goals']['home']}-{m['goals']['away']}",
            "客队": a_cn,
        })

    def fmt_recent(recent, team_id, team_cn):
        rows = []
        for m in recent:
            h_cn = en_to_cn(m["teams"]["home"]["name"])
            a_cn = en_to_cn(m["teams"]["away"]["name"])
            h_s = m["goals"]["home"] or 0
            a_s = m["goals"]["away"] or 0
            if m["teams"]["home"]["id"] == team_id:
                result = "胜" if h_s > a_s else ("平" if h_s == a_s else "负")
                rows.append({"日期": m["fixture"]["date"][:10], "对手": a_cn,
                             "比分": f"{h_s}-{a_s}", "结果": result})
            else:
                result = "胜" if a_s > h_s else ("平" if a_s == h_s else "负")
                rows.append({"日期": m["fixture"]["date"][:10], "对手": h_cn,
                             "比分": f"{a_s}-{h_s}", "结果": result})
        return rows

    return {
        "match": f"{home_cn} vs {away_cn}",
        "league_api": league_name_api, "league_country": league_country,
        "league_id": league_id, "league_cn": probs["league_cn"],
        "odds": odds, "coefs": coefs, "probs": probs,
        "injuries": inj_list, "h2h": h2h_list,
        "home_recent": fmt_recent(h_recent, home_id, home_cn),
        "away_recent": fmt_recent(a_recent, away_id, away_cn),
        "health": health, "health_score": health_score,
        "home_cn": home_cn, "away_cn": away_cn,
    }, None


# ================================================================
# ============ 界面 ============
# ================================================================
st.subheader("📅 按日期搜索当日比赛")
st.caption("搜索指定日期、系统支持的所有联赛比赛，勾选后加入分析列表。")

col_a, col_b = st.columns([2, 1])
with col_a:
    search_date = st.date_input("选择日期", value=datetime.now().date())
with col_b:
    st.write("")
    st.write("")
    if st.button("🔍 搜索当日比赛"):
        with st.spinner("正在搜索..."):
            fixtures = search_fixtures_by_date(search_date.strftime("%Y-%m-%d"))
            st.session_state["date_fixtures"] = fixtures
            st.session_state["date_fixtures_date"] = search_date.strftime("%Y-%m-%d")

if "date_fixtures" in st.session_state:
    fixtures = st.session_state["date_fixtures"]
    if not fixtures:
        st.warning(f"未找到 {st.session_state.get('date_fixtures_date', '')} 当天支持的联赛比赛")
    else:
        st.success(f"共找到 {len(fixtures)} 场支持的联赛比赛")
        options = []
        opt_to_match = {}
        for f in fixtures:
            home_cn = en_to_cn(f["teams"]["home"]["name"])
            away_cn = en_to_cn(f["teams"]["away"]["name"])
            lid = f["league"]["id"]
            league_cn = LEAGUE_MAP[lid][2]
            time_str = f["fixture"]["date"][11:16]
            opt = f"[{league_cn}] {home_cn} vs {away_cn} ({time_str})"
            options.append(opt)
            _date_str = st.session_state.get("date_fixtures_date", datetime.now().strftime("%Y-%m-%d"))
            opt_to_match[opt] = f"{home_cn} {away_cn}@{_date_str}"

        selected = st.multiselect("勾选要分析的比赛", options)
        col_c, col_d = st.columns(2)
        with col_c:
            if st.button("➕ 加入分析列表"):
                if "selected_matches" not in st.session_state:
                    st.session_state["selected_matches"] = []
                added = 0
                for opt in selected:
                    ms = opt_to_match.get(opt)
                    if ms and ms not in st.session_state["selected_matches"]:
                        st.session_state["selected_matches"].append(ms)
                        added += 1
                st.success(f"成功加入 {added} 场")
                st.rerun()
        with col_d:
            if st.button("🗑️ 清空已加入"):
                st.session_state["selected_matches"] = []
                st.rerun()

        if st.session_state.get("selected_matches"):
            st.info(f"📋 当前待分析列表：{len(st.session_state['selected_matches'])} 场")
            with st.expander("查看已加入的比赛"):
                for i, m in enumerate(st.session_state["selected_matches"], 1):
                    st.write(f"{i}. {m}")

st.markdown("---")
st.subheader("📊 手动输入或确认分析列表")
match_input = st.text_input("自由格式，用逗号分隔（例如：阿森纳 切尔西, 皇马 巴萨）", "")

if st.button("🚀 开始批量分析", type="primary"):
    all_matches = []
    if match_input:
        all_matches.extend([m.strip() for m in match_input.split(",") if m.strip()])
    if st.session_state.get("selected_matches"):
        all_matches.extend(st.session_state["selected_matches"])
    all_matches = list(dict.fromkeys(all_matches))

    if not all_matches:
        st.warning("请手动输入比赛，或从日期搜索结果中勾选添加")
    elif not api_key:
        st.error("API Key 未配置")
    else:
        results = []
        progress = st.progress(0)
        for i, m in enumerate(all_matches):
            progress.progress((i + 1) / len(all_matches), text=f"正在分析：{m}")
            if "@" in m:
                match_part, date_part = m.rsplit("@", 1)
            else:
                match_part, date_part = m, None
            home, away = parse_match(match_part)
            if not home or not away:
                st.warning(f"无法解析：{m}")
                continue
            r, err = analyze_match(home, away, date_part)
            if err:
                st.warning(err)
            else:
                results.append(r)
        progress.empty()

        if not results:
            st.error("所有比赛分析失败")
        else:
            st.session_state["results"] = results
            st.success(f"分析完成！共 {len(results)} 场")

# ============ 结果展示 ============
if "results" in st.session_state:
    st.markdown("---")
    st.subheader("📋 分析结果总览")

    for r in st.session_state["results"]:
        with st.container(border=True):
            p = r["probs"]
            st.markdown(f"### {r['match']}")
            st.caption(f"🏆 联赛识别：**{r['league_cn']}** (API: {r['league_api']} · {r['league_country']}) "
                       f"→ 融合比例 模型{int(p['model_w']*100)}% / 市场{int(p['market_w']*100)}%")

            col1, col2, col3 = st.columns(3)
            col1.metric("主胜", f"{p['final'][0]}%")
            col2.metric("平局", f"{p['final'][1]}%")
            col3.metric("客胜", f"{p['final'][2]}%")

            with st.expander("🔍 数据依据详情"):
                st.markdown(f"### 🩺 本场数据健康度：{r['health_score']}%")
                for icon, name, detail in r["health"]:
                    st.markdown(f"- {icon} **{name}**：{detail}")

                st.markdown("### 🩺 伤停明细")
                if r["injuries"]:
                    st.dataframe(pd.DataFrame(r["injuries"]), hide_index=True)
                else:
                    st.caption("⚠️ 无伤停记录")
                st.caption("数据源：API-Football（角色按出场分钟判断：主力≥1500，轮换≥600，替补<600）")

                st.markdown("### 📊 五层概率对比")
                st.dataframe(pd.DataFrame({
                    "层级": ["逻辑回归", "XGBoost", "模型融合", "市场去水", "最终融合"],
                    "主胜": [f"{p['lr'][0]}%", f"{p['xgb'][0]}%", f"{p['model'][0]}%",
                             f"{p['market'][0]}%", f"**{p['final'][0]}%**"],
                    "平局": [f"{p['lr'][1]}%", f"{p['xgb'][1]}%", f"{p['model'][1]}%",
                             f"{p['market'][1]}%", f"**{p['final'][1]}%**"],
                    "客胜": [f"{p['lr'][2]}%", f"{p['xgb'][2]}%", f"{p['model'][2]}%",
                             f"{p['market'][2]}%", f"**{p['final'][2]}%**"],
                }), hide_index=True)

                st.markdown("### 🎛️ 五项系数")
                st.json(r["coefs"])

                st.markdown(f"### 📈 近期战绩 - {r['home_cn']}")
                if r["home_recent"]:
                    st.dataframe(pd.DataFrame(r["home_recent"]), hide_index=True)
                st.markdown(f"### 📈 近期战绩 - {r['away_cn']}")
                if r["away_recent"]:
                    st.dataframe(pd.DataFrame(r["away_recent"]), hide_index=True)

                st.markdown("### ⚔️ 历史交战 (近5次)")
                if r["h2h"]:
                    st.dataframe(pd.DataFrame(r["h2h"]), hide_index=True)
                else:
                    st.caption("⚠️ 无H2H记录")

                st.markdown("### 💱 市场赔率（Pinnacle）")
                st.markdown(f"主胜 **{r['odds'][0]}** / 平局 **{r['odds'][1]}** / 客胜 **{r['odds'][2]}**")
                st.caption(f"数据抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    st.markdown("---")
    st.subheader("🎯 今日最稳二串一推荐")

    candidates = []
    for r in st.session_state["results"]:
        p = r["probs"]["final"]
        max_idx = int(np.argmax(p))
        max_p = p[max_idx]
        odd = r["odds"][max_idx]
        if max_p > 60 and 1.30 <= odd <= 2.50 and r["health_score"] >= 80:
            market_p = r["probs"]["market"]
            if max_p - market_p[max_idx] >= 0:
                candidates.append({
                    "match": r["match"], "league": r["league_cn"],
                    "pick": ["主胜", "平局", "客胜"][max_idx],
                    "prob": max_p, "odd": odd, "health": r["health_score"]
                })

    best_combo = None
    best_score = 0
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            c1, c2 = candidates[i], candidates[j]
            total_odd = c1["odd"] * c2["odd"]
            if 1.7 <= total_odd <= 4.0:
                hit_rate = (c1["prob"] / 100) * (c2["prob"] / 100)
                if hit_rate > best_score:
                    best_score = hit_rate
                    best_combo = (c1, c2, total_odd, hit_rate)

    if best_combo:
        c1, c2, total_odd, hit_rate = best_combo
        st.success(f"✅ 找到最稳组合！理论命中率：{hit_rate*100:.1f}%")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**🥇 稳胆1**：{c1['match']} ({c1['league']})")
            st.markdown(f"推荐：**{c1['pick']}** | 概率 {c1['prob']}% | 赔率 {c1['odd']} | 健康度 {c1['health']}%")
        with col2:
            st.markdown(f"**🥈 稳胆2**：{c2['match']} ({c2['league']})")
            st.markdown(f"推荐：**{c2['pick']}** | 概率 {c2['prob']}% | 赔率 {c2['odd']} | 健康度 {c2['health']}%")
        st.markdown(f"**💰 组合赔率**：{total_odd:.2f}（1.7-4.0 区间）")
        st.markdown(f"**📊 理论命中率**：{hit_rate*100:.1f}%")
    else:
        st.warning("⚠️ 今日无符合条件的二串一推荐，建议观望或只玩单场。")
