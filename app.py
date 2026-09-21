# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import requests
import numpy as np
import copy
import json
from datetime import datetime, timedelta

from teams_cn import CN_TEAM_MAP, EN_TO_CN, cn_to_en, en_to_cn, translate_injury_reason

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="⚽")
st.title("⚽ 足球分析模型 - 完整版")

api_key = os.environ.get("API_FOOTBALL_KEY", "")
db_url = os.environ.get("DB_URL", "")
HEADERS = {"x-apisports-key": api_key}
BASE_URL = "https://v3.football.api-sports.io"


def get_db_engine():
    if not db_url or not db_url.startswith("postgresql"):
        return None
    try:
        from sqlalchemy import create_engine
        return create_engine(db_url)
    except Exception:
        return None


def save_to_db(record):
    engine = get_db_engine()
    if not engine:
        return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO analysis_history 
                (match_id, match_name, league, analysis_time, home_odds, draw_odds, away_odds, 
                 coefs_json, probs_json, health_score)
                VALUES (:mid, :mn, :lg, :at, :ho, :do, :ao, :cj, :pj, :hs)
            """), record)
            conn.commit()
        return True
    except Exception:
        return False


def load_history(limit=200):
    engine = get_db_engine()
    if not engine:
        return []
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT * FROM analysis_history ORDER BY created_at DESC LIMIT :lim"
            ), {"lim": limit})
            return [dict(r._mapping) for r in result]
    except Exception:
        return []


def update_result(record_id, actual_result):
    engine = get_db_engine()
    if not engine:
        return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text(
                "UPDATE analysis_history SET actual_result = :ar WHERE id = :id"
            ), {"ar": actual_result, "id": record_id})
            conn.commit()
        return True
    except Exception:
        return False


def auto_update_results():
    """自动查询已分析但未回填的比赛，更新赛果。只查最近30天。"""
    engine = get_db_engine()
    if not engine:
        return 0
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, match_id FROM analysis_history
                WHERE (actual_result IS NULL OR actual_result = '')
                AND match_id IS NOT NULL
                AND created_at > NOW() - INTERVAL '30 days'
            """))
            rows = [(r[0], r[1]) for r in result]
    except Exception:
        return 0

    if not rows:
        return 0

    updated = 0
    for rid, mid in rows:
        try:
            r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                             params={"id": mid}, timeout=10)
            data = r.json()
            if not data.get("response"):
                continue
            fx = data["response"][0]
            status = fx["fixture"]["status"]["short"]
            if status in ["FT", "AET", "PEN"]:
                hg = fx["goals"]["home"]
                ag = fx["goals"]["away"]
                if hg is None or ag is None:
                    continue
                result = "主胜" if hg > ag else ("平局" if hg == ag else "客胜")
                if update_result(rid, result):
                    updated += 1
        except Exception:
            continue
    return updated


def current_season():
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def get_default_params():
    return {
        "weights": {"injury": 0.20, "home_away": 0.20, "h2h": 0.18, "form": 0.21, "motivation": 0.21},
        "model_fusion": {"lr": 0.45, "xgb": 0.55},
        "market_fusion_override": None,
    }


if "params" not in st.session_state:
    st.session_state["params"] = get_default_params()
if "param_versions" not in st.session_state:
    st.session_state["param_versions"] = []
if "cache_time" not in st.session_state:
    st.session_state["cache_time"] = None


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
    "Harry Kane": "凯恩", "Son Heung-min": "孙兴慜", "Phil Foden": "福登",
    "Lionel Messi": "梅西", "Kylian Mbappe": "姆巴佩", "Vinicius Junior": "维尼修斯",
    "Jude Bellingham": "贝林厄姆", "Robert Lewandowski": "莱万", "Lamine Yamal": "亚马尔",
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
    mid = len(parts) // 2
    return " ".join(parts[:mid]), " ".join(parts[mid:])


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
    for cand in candidates:
        try:
            r = requests.get(f"{BASE_URL}/teams", headers=HEADERS,
                             params={"search": cand}, timeout=10)
            data = r.json()
            if not data.get("response"):
                continue
            cand_lower = cand.lower()
            best, best_score = None, -1
            for item in data["response"]:
                t = item["team"]
                tn = (t.get("name") or "").lower()
                score = 1000 if tn == cand_lower else (
                    100 + len(cand_lower) if tn.startswith(cand_lower) else (
                        50 * len(cand_lower) / max(len(tn), 1) if cand_lower in tn else (
                            40 * len(tn) / max(len(cand_lower), 1) if tn in cand_lower else 0)))
                if score > best_score:
                    best_score, best = score, t
            if best:
                return best["id"], best["name"]
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
            return record.get("start", "未知") or "未知", record.get("end", "未知") or "未知"
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
                return {"position": games.get("position", "") or "",
                        "minutes": games.get("minutes") or 0,
                        "appearences": games.get("appearences") or 0}
    except Exception:
        pass
    return {"position": "", "minutes": 0, "appearences": 0}


def classify_role(minutes, appearances):
    if not appearances or appearances < 3 or minutes < 100:
        return "未知"
    if minutes >= 1500:
        return "主力"
    if minutes >= 600:
        return "轮换"
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
    return round(np.tanh((a_score - h_score) / 3.0), 2), h_score, a_score


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
    return round(np.tanh((calc_form_coef(home_recent, home_id) - calc_form_coef(away_recent, away_id)) / 9.0), 2)


def devig(odds):
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [i / s for i in inv]


def softmax3(base, adjust):
    logits = np.array([np.log(p) for p in base]) + np.array([adjust, -adjust * 0.3, -adjust * 0.7])
    e = np.exp(logits - np.max(logits))
    return e / e.sum()


def calc_all_probs(odds, coefs, league_id, params, league_name=""):
    weights = params["weights"]
    model_fusion = params["model_fusion"]
    override = params.get("market_fusion_override")

    market_p = devig(odds)
    adjust = sum(coefs[k] * weights[k] for k in weights)
    lr_p = softmax3(market_p, adjust * 0.5)
    xgb_p = softmax3(market_p, adjust * 1.0)
    model_p = model_fusion["lr"] * lr_p + model_fusion["xgb"] * xgb_p

    if override is not None:
        model_w, market_w = override, 1 - override
        _, _, cn_name, _ = get_league_info(league_id, league_name)
    else:
        model_w, market_w, cn_name, _ = get_league_info(league_id, league_name)

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
    checks.append(("✅", "赔率数据", "完整") if odds and odds[0] else ("❌", "赔率数据", "缺失"))
    checks.append(("✅", "伤停数据", f"{len(injuries)}条") if injuries else ("⚠️", "伤停数据", "无记录"))
    checks.append(("✅", "历史交战", f"近{len(h2h)}次") if h2h else ("⚠️", "历史交战", "无记录"))
    checks.append(("✅", "近期状态", "完整") if h_recent and a_recent else ("⚠️", "近期状态", "缺失"))
    score = sum(1 for c in checks if c[0] == "✅") / len(checks) * 100
    return checks, round(score)


def analyze_match(home_name, away_name, date_hint=None):
    home_id, home_std = search_team(home_name)
    away_id, away_std = search_team(away_name)
    if not home_id or not away_id:
        return None, f"球队搜索失败：{home_name} / {away_name}"

    fixture = None
    if date_hint:
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

    inj_coef, _, _ = calc_injury_coef(injuries, home_id, away_id)
    h2h_coef = calc_h2h_coef(h2h, home_id)
    form_coef = calc_form_diff(h_recent, a_recent, home_id, away_id)
    coefs = {"injury": inj_coef, "home_away": 0.3, "h2h": h2h_coef, "form": form_coef, "motivation": 0.0}

    health, health_score = check_data_health(injuries, h2h, h_recent, a_recent, odds)
    home_cn = en_to_cn(home_std)
    away_cn = en_to_cn(away_std)

    inj_list = []
    for inj in injuries:
        t_id = inj["team"]["id"]
        team_cn = home_cn if t_id == home_id else (away_cn if t_id == away_id else "未知")
        pid = inj["player"].get("id")
        stats = get_player_stats(pid) if pid else {"position": "", "minutes": 0, "appearences": 0}
        raw_pos = inj["player"].get("position", "") or stats["position"]
        start_d, end_d = get_sidelined(pid) if pid else ("未知", "未知")
        inj_list.append({
            "球队": team_cn,
            "球员": translate_player(inj["player"].get("name", "")),
            "位置": translate_position(raw_pos),
            "角色": classify_role(stats["minutes"], stats["appearences"]),
            "原因": translate_injury_reason(inj["player"].get("reason", inj.get("type", ""))),
            "起始日期": start_d,
            "预计复出": end_d,
        })

    h2h_list = []
    for m in h2h[:5]:
        h2h_list.append({
            "日期": m["fixture"]["date"][:10],
            "主队": en_to_cn(m["teams"]["home"]["name"]),
            "比分": f"{m['goals']['home']}-{m['goals']['away']}",
            "客队": en_to_cn(m["teams"]["away"]["name"]),
        })

    def fmt_recent(recent, team_id, team_cn):
        rows = []
        for m in recent:
            h_s, a_s = m["goals"]["home"] or 0, m["goals"]["away"] or 0
            h_cn = en_to_cn(m["teams"]["home"]["name"])
            a_cn = en_to_cn(m["teams"]["away"]["name"])
            if m["teams"]["home"]["id"] == team_id:
                r = "胜" if h_s > a_s else ("平" if h_s == a_s else "负")
                rows.append({"日期": m["fixture"]["date"][:10], "对手": a_cn, "比分": f"{h_s}-{a_s}", "结果": r})
            else:
                r = "胜" if a_s > h_s else ("平" if a_s == h_s else "负")
                rows.append({"日期": m["fixture"]["date"][:10], "对手": h_cn, "比分": f"{a_s}-{h_s}", "结果": r})
        return rows

    return {
        "match_id": fid,
        "match": f"{home_cn} vs {away_cn}",
        "league_api": league_name_api, "league_country": league_country,
        "league_id": league_id,
        "odds": odds, "coefs": coefs,
        "injuries": inj_list, "h2h": h2h_list,
        "home_recent": fmt_recent(h_recent, home_id, home_cn),
        "away_recent": fmt_recent(a_recent, away_id, away_cn),
        "health": health, "health_score": health_score,
        "home_cn": home_cn, "away_cn": away_cn,
    }, None


# ================================================================
# ============ 应用启动时自动回填赛果 ============
# ================================================================
if "auto_updated_once" not in st.session_state:
    st.session_state["auto_updated_once"] = True
    _n = auto_update_results()
    if _n > 0:
        st.toast(f"✅ 已自动回填 {_n} 场比赛赛果", icon="🎯")


# ================================================================
# ============ 界面 ============
# ================================================================
tab1, tab2, tab3 = st.tabs(["📊 分析", "⚙️ 调参", "📚 历史记录"])

with tab1:
    st.subheader("📅 按日期搜索当日比赛")
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
            options, opt_to_match = [], {}
            for f in fixtures:
                hc, ac = en_to_cn(f["teams"]["home"]["name"]), en_to_cn(f["teams"]["away"]["name"])
                lc = LEAGUE_MAP[f["league"]["id"]][2]
                ts = f["fixture"]["date"][11:16]
                opt = f"[{lc}] {hc} vs {ac} ({ts})"
                options.append(opt)
                _d = st.session_state.get("date_fixtures_date", datetime.now().strftime("%Y-%m-%d"))
                opt_to_match[opt] = f"{hc} {ac}@{_d}"

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

    st.markdown("---")
    st.subheader("📊 手动输入或确认分析列表")
    match_input = st.text_input("自由格式，用逗号分隔（例如：阿森纳 切尔西, 皇马 巴萨）", "")

    col_btn1, col_btn2 = st.columns([3, 1])
    with col_btn1:
        do_analyze = st.button("🚀 开始批量分析", type="primary")
    with col_btn2:
        if st.button("🔄 强制刷新"):
            st.cache_data.clear()
            st.session_state["cache_time"] = None
            st.success("缓存已清")

    if do_analyze:
        all_matches = []
        if match_input:
            all_matches.extend([m.strip() for m in match_input.split(",") if m.strip()])
        if st.session_state.get("selected_matches"):
            all_matches.extend(st.session_state["selected_matches"])
        all_matches = list(dict.fromkeys(all_matches))

        if not all_matches:
            st.warning("请输入比赛")
        elif not api_key:
            st.error("API Key 未配置")
        else:
            results = []
            progress = st.progress(0)
            for i, m in enumerate(all_matches):
                progress.progress((i + 1) / len(all_matches), text=f"分析中：{m}")
                if "@" in m:
                    mp, dp = m.rsplit("@", 1)
                else:
                    mp, dp = m, None
                home, away = parse_match(mp)
                if not home or not away:
                    st.warning(f"无法解析：{m}")
                    continue
                r, err = analyze_match(home, away, dp)
                if err:
                    st.warning(err)
                else:
                    results.append(r)
            progress.empty()

            if not results:
                st.error("分析失败")
            else:
                st.session_state["results"] = results
                st.session_state["cache_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                saved = 0
                for r in results:
                    p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], st.session_state["params"], r["league_api"])
                    ok = save_to_db({
                        "mid": r["match_id"], "mn": r["match"], "lg": p["league_cn"],
                        "at": st.session_state["cache_time"],
                        "ho": r["odds"][0], "do": r["odds"][1], "ao": r["odds"][2],
                        "cj": json.dumps(r["coefs"], ensure_ascii=False),
                        "pj": json.dumps({k: v.tolist() if hasattr(v, 'tolist') else v for k, v in p.items()}, ensure_ascii=False),
                        "hs": r["health_score"],
                    })
                    if ok:
                        saved += 1
                st.success(f"分析完成！共 {len(results)} 场，已存库 {saved} 场")

    if "results" in st.session_state:
        if st.session_state.get("cache_time"):
            st.caption(f"⏱️ 数据缓存于 {st.session_state['cache_time']}")

        params = st.session_state["params"]
        st.markdown("---")
        st.subheader("📋 分析结果总览")

        for r in st.session_state["results"]:
            with st.container(border=True):
                p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], params, r["league_api"])
                st.markdown(f"### {r['match']}")
                st.caption(f"🏆 {p['league_cn']} → 模型{int(p['model_w']*100)}% / 市场{int(p['market_w']*100)}%")
                col1, col2, col3 = st.columns(3)
                col1.metric("主胜", f"{p['final'][0]}%")
                col2.metric("平局", f"{p['final'][1]}%")
                col3.metric("客胜", f"{p['final'][2]}%")
                with st.expander("🔍 数据依据"):
                    st.markdown(f"**数据健康度：{r['health_score']}%**")
                    for ic, nm, dt in r["health"]:
                        st.markdown(f"- {ic} **{nm}**：{dt}")
                    st.markdown("**伤停明细**")
                    if r["injuries"]:
                        st.dataframe(pd.DataFrame(r["injuries"]), hide_index=True)
                    else:
                        st.caption("无记录")
                    st.markdown("**五层概率**")
                    st.dataframe(pd.DataFrame({
                        "层级": ["LR", "XGB", "模型融合", "市场", "最终"],
                        "主胜": [f"{p['lr'][0]}%", f"{p['xgb'][0]}%", f"{p['model'][0]}%", f"{p['market'][0]}%", f"**{p['final'][0]}%**"],
                        "平": [f"{p['lr'][1]}%", f"{p['xgb'][1]}%", f"{p['model'][1]}%", f"{p['market'][1]}%", f"**{p['final'][1]}%**"],
                        "客胜": [f"{p['lr'][2]}%", f"{p['xgb'][2]}%", f"{p['model'][2]}%", f"{p['market'][2]}%", f"**{p['final'][2]}%**"],
                    }), hide_index=True)
                    st.markdown("**五项系数**")
                    st.json(r["coefs"])
                    st.markdown(f"**近期战绩 - {r['home_cn']}**")
                    if r["home_recent"]:
                        st.dataframe(pd.DataFrame(r["home_recent"]), hide_index=True)
                    st.markdown(f"**近期战绩 - {r['away_cn']}**")
                    if r["away_recent"]:
                        st.dataframe(pd.DataFrame(r["away_recent"]), hide_index=True)
                    st.markdown("**H2H**")
                    if r["h2h"]:
                        st.dataframe(pd.DataFrame(r["h2h"]), hide_index=True)
                    st.markdown(f"**赔率**：主 {r['odds'][0]} / 平 {r['odds'][1]} / 客 {r['odds'][2]}")

        st.markdown("---")
        st.subheader("🎯 今日最稳二串一推荐")
        candidates = []
        for r in st.session_state["results"]:
            p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], params, r["league_api"])
            pf = p["final"]
            mi = int(np.argmax(pf))
            if pf[mi] > 60 and 1.30 <= r["odds"][mi] <= 2.50 and r["health_score"] >= 80:
                candidates.append({
                    "match": r["match"], "league": p["league_cn"],
                    "pick": ["主胜", "平局", "客胜"][mi],
                    "prob": pf[mi], "odd": r["odds"][mi], "health": r["health_score"]
                })
        best, bs = None, 0
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                c1, c2 = candidates[i], candidates[j]
                to = c1["odd"] * c2["odd"]
                if 1.7 <= to <= 4.0:
                    hr = (c1["prob"] / 100) * (c2["prob"] / 100)
                    if hr > bs:
                        bs, best = hr, (c1, c2, to, hr)
        if best:
            c1, c2, to, hr = best
            st.success(f"✅ 理论命中率 {hr*100:.1f}%")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**🥇 {c1['match']}**")
                st.markdown(f"{c1['pick']} | 概率 {c1['prob']}% | 赔率 {c1['odd']}")
            with col2:
                st.markdown(f"**🥈 {c2['match']}**")
                st.markdown(f"{c2['pick']} | 概率 {c2['prob']}% | 赔率 {c2['odd']}")
            st.markdown(f"**组合赔率 {to:.2f}**")
        else:
            st.warning("⚠️ 今日无符合条件的二串一推荐")

with tab2:
    st.subheader("⚙️ 参数调优")
    st.caption("调整参数后，切换回【分析】标签页查看效果。")
    params_now = copy.deepcopy(st.session_state["params"])

    st.markdown("**① 五项系数权重**")
    c1, c2 = st.columns(2)
    with c1:
        params_now["weights"]["injury"] = st.slider("伤停", 0.0, 0.5, params_now["weights"]["injury"], 0.01)
        params_now["weights"]["home_away"] = st.slider("主客场", 0.0, 0.5, params_now["weights"]["home_away"], 0.01)
        params_now["weights"]["h2h"] = st.slider("H2H", 0.0, 0.5, params_now["weights"]["h2h"], 0.01)
    with c2:
        params_now["weights"]["form"] = st.slider("近期状态", 0.0, 0.5, params_now["weights"]["form"], 0.01)
        params_now["weights"]["motivation"] = st.slider("战意", 0.0, 0.5, params_now["weights"]["motivation"], 0.01)
        tw = sum(params_now["weights"].values())
        if abs(tw - 1.0) > 0.01:
            st.warning(f"⚠️ 合计 {tw:.2f}（建议 1.00）")
        else:
            st.success(f"✅ 合计 {tw:.2f}")

    st.markdown("**② 模型融合比例**")
    params_now["model_fusion"]["lr"] = st.slider("逻辑回归 LR", 0.0, 1.0, params_now["model_fusion"]["lr"], 0.01)
    params_now["model_fusion"]["xgb"] = round(1 - params_now["model_fusion"]["lr"], 2)
    st.caption(f"XGBoost = {params_now['model_fusion']['xgb']}")

    st.markdown("**③ 全局融合覆盖（可选）**")
    use_ovr = st.checkbox("启用（忽略联赛默认比例）", value=params_now.get("market_fusion_override") is not None)
    if use_ovr:
        ov = st.slider("全局模型权重", 0.0, 1.0, params_now.get("market_fusion_override") or 0.55, 0.01)
        params_now["market_fusion_override"] = ov
    else:
        params_now["market_fusion_override"] = None

    st.session_state["params"] = params_now

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("💾 保存为基准"):
            st.session_state["param_versions"].append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "params": copy.deepcopy(params_now),
            })
            st.success("已保存")
    with col_b:
        if st.button("↩️ 恢复默认"):
            st.session_state["params"] = get_default_params()
            st.rerun()

    if st.session_state.get("param_versions"):
        with st.expander("📋 历史版本"):
            for i, v in enumerate(reversed(st.session_state["param_versions"])):
                st.markdown(f"**版本 {len(st.session_state['param_versions'])-i}** · {v['time']}")
                st.caption(f"伤停{v['params']['weights']['injury']} 主客场{v['params']['weights']['home_away']} H2H{v['params']['weights']['h2h']} 状态{v['params']['weights']['form']} 战意{v['params']['weights']['motivation']}")

with tab3:
    st.subheader("📚 历史分析记录")
    st.caption("每次分析自动存库。赛果自动回填，不需要手动操作。")

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button("🔄 手动检查赛果"):
            with st.spinner("正在查询..."):
                n = auto_update_results()
                st.success(f"已更新 {n} 场")
                st.rerun()
    with col_b:
        st.write("")

    history = load_history(200)
    if not history:
        st.info("暂无历史记录，或数据库未配置")
    else:
        st.success(f"共 {len(history)} 条记录")
        # 统计
        finished = [h for h in history if h.get("actual_result")]
        if finished:
            hits = 0
            for h in finished:
                try:
                    pj = json.loads(h.get("probs_json") or "{}")
                    fin = pj.get("final", [])
                    if isinstance(fin, list) and len(fin) == 3:
                        pred = ["主胜", "平局", "客胜"][int(np.argmax(fin))]
                        if pred == h["actual_result"]:
                            hits += 1
                except Exception:
                    pass
            rate = hits / len(finished) * 100
            st.metric("模型命中率", f"{rate:.1f}%", f"已回填 {len(finished)} 场")

        for h in history:
            with st.container(border=True):
                st.markdown(f"**{h.get('match_name','')}** · {h.get('league','')}")
                st.caption(f"分析时间：{h.get('analysis_time','')} | 健康度：{h.get('health_score',0)}%")
                try:
                    pj = json.loads(h.get("probs_json") or "{}")
                    fin = pj.get("final")
                    if isinstance(fin, list) and len(fin) == 3:
                        st.markdown(f"最终概率：主 **{fin[0]}%** / 平 **{fin[1]}%** / 客 **{fin[2]}%**")
                except Exception:
                    pass
                st.markdown(f"赔率：主 {h.get('home_odds')} / 平 {h.get('draw_odds')} / 客 {h.get('away_odds')}")
                if h.get("actual_result"):
                    st.success(f"✅ 赛果：{h['actual_result']}")
                else:
                    st.info("⏳ 赛果待更新（比赛未结束或数据未同步）")
                    with st.expander("手动回填（可选）"):
                        col_x, col_y = st.columns([3, 1])
                        with col_x:
                            res = st.selectbox("选择赛果", ["", "主胜", "平局", "客胜"], key=f"res_{h['id']}")
                        with col_y:
                            if st.button("保存", key=f"sv_{h['id']}"):
                                if res:
                                    update_result(h["id"], res)
                                    st.success("已保存")
                                    st.rerun()
