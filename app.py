# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import requests
import numpy as np
import copy
import json
import re
import pickle
import base64
import io
from datetime import datetime, timedelta
from scipy.stats import poisson
from scipy.optimize import minimize
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss
from xgboost import XGBClassifier

from teams_cn import CN_TEAM_MAP, EN_TO_CN, cn_to_en, en_to_cn, translate_injury_reason

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="⚽")
st.title("⚽ 足球分析模型 - 完整版")

api_key = os.environ.get("API_FOOTBALL_KEY", "")
db_url = os.environ.get("DB_URL", "")
HEADERS = {"x-apisports-key": api_key}
BASE_URL = "https://v3.football.api-sports.io"

# ============ 训练用联赛代码映射 ============
LEAGUE_CODE_MAP = {
    "英超": "E0", "英冠": "E1", "西甲": "SP1", "西乙": "SP2",
    "德甲": "D1", "德乙": "D2", "意甲": "I1", "意乙": "I2",
    "法甲": "F1", "法乙": "F2", "荷甲": "N1", "葡超": "P1",
    "比甲": "B1", "苏超": "SC0", "挪超": "NOR", "瑞超": "SWE",
    "丹超": "DNK", "芬超": "FIN",
}
TRAINING_SEASONS = ["2223", "2324", "2425"]  # 近3个赛季


# ============ 数据库操作 ============
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


# ============ 模型保存/加载 ============
def save_model_to_db(blob_base64, metrics):
    engine = get_db_engine()
    if not engine:
        return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # 清空旧模型，只保留最新
            conn.execute(text("DELETE FROM model_storage"))
            conn.execute(text("""
                INSERT INTO model_storage (model_blob, samples, lr_logloss, xgb_logloss, notes)
                VALUES (:b, :s, :lr, :xgb, :n)
            """), {
                "b": blob_base64,
                "s": metrics.get("samples", 0),
                "lr": metrics.get("lr_logloss", 0),
                "xgb": metrics.get("xgb_logloss", 0),
                "n": metrics.get("notes", ""),
            })
            conn.commit()
        return True
    except Exception:
        return False


def load_model_from_db():
    engine = get_db_engine()
    if not engine:
        return None
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT model_blob, trained_at, samples, lr_logloss, xgb_logloss FROM model_storage ORDER BY id DESC LIMIT 1"
            ))
            row = result.fetchone()
            if not row:
                return None
            blob = row[0]
            model = deserialize_model(blob)
            return {
                "model": model,
                "trained_at": str(row[1]),
                "samples": row[2],
                "lr_logloss": row[3],
                "xgb_logloss": row[4],
            }
    except Exception:
        return None


# ============ 训练相关 ============
def download_league_csv(league_cn, seasons=TRAINING_SEASONS):
    code = LEAGUE_CODE_MAP.get(league_cn)
    if not code:
        return None
    dfs = []
    for season in seasons:
        url = f"https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200 and len(r.content) > 200:
                df = pd.read_csv(io.BytesIO(r.content), encoding='latin1', on_bad_lines='skip')
                if 'FTHG' in df.columns and 'FTAG' in df.columns:
                    df['league_cn'] = league_cn
                    df['season'] = season
                    dfs.append(df)
        except Exception:
            continue
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


def preprocess_df(df):
    """提取特征：赔率去水 + 赔率漂移"""
    needed = ['B365H', 'B365D', 'B365A', 'FTHG', 'FTAG']
    for c in needed:
        if c not in df.columns:
            return None, None
    df = df.dropna(subset=needed).copy()
    if len(df) < 30:
        return None, None

    odds = df[['B365H', 'B365D', 'B365A']].values.astype(float)
    inv = 1.0 / odds
    probs = inv / inv.sum(axis=1, keepdims=True)
    df['p_home'] = probs[:, 0]
    df['p_draw'] = probs[:, 1]
    df['p_away'] = probs[:, 2]

    # 收盘赔率（如果有）
    if all(c in df.columns for c in ['B365CH', 'B365CD', 'B365CA']):
        odds_c = df[['B365CH', 'B365CD', 'B365CA']].values.astype(float)
        inv_c = 1.0 / odds_c
        probs_c = inv_c / inv_c.sum(axis=1, keepdims=True)
        df['drift_home'] = probs_c[:, 0] - probs[:, 0]
        df['drift_away'] = probs_c[:, 2] - probs[:, 2]
        df['p_home_close'] = probs_c[:, 0]
        df['p_draw_close'] = probs_c[:, 1]
        df['p_away_close'] = probs_c[:, 2]
    else:
        df['p_home_close'] = df['p_home']
        df['p_draw_close'] = df['p_draw']
        df['p_away_close'] = df['p_away']
        df['drift_home'] = 0.0
        df['drift_away'] = 0.0

    df['result'] = df.apply(lambda r: 0 if r['FTHG'] > r['FTAG'] else (1 if r['FTHG'] == r['FTAG'] else 2), axis=1)
    feature_cols = ['p_home', 'p_draw', 'p_away',
                    'p_home_close', 'p_draw_close', 'p_away_close',
                    'drift_home', 'drift_away']
    return df, feature_cols


def train_models(df, feature_cols):
    X = df[feature_cols].values
    y = df['result'].values

    # 按时间顺序切分 80/20
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    lr = LogisticRegression(multi_class='multinomial', solver='lbfgs',
                            max_iter=1000, class_weight='balanced')
    lr.fit(X_train_s, y_train)

    xgb = XGBClassifier(
        objective='multi:softprob', num_class=3,
        n_estimators=200, max_depth=4, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        eval_metric='mlogloss', verbosity=0, use_label_encoder=False
    )
    xgb.fit(X_train, y_train)

    try:
        lr_proba = lr.predict_proba(X_test_s)
        xgb_proba = xgb.predict_proba(X_test)
        lr_loss = float(log_loss(y_test, lr_proba))
        xgb_loss = float(log_loss(y_test, xgb_proba))
    except Exception:
        lr_loss, xgb_loss = 0, 0

    metrics = {
        "samples": len(df),
        "train": split,
        "test": len(X) - split,
        "lr_logloss": lr_loss,
        "xgb_logloss": xgb_loss,
        "notes": f"联赛数 {df['league_cn'].nunique()}，赛季 {df['season'].nunique()}",
    }
    return lr, scaler, xgb, metrics


def serialize_model(lr, scaler, xgb):
    blob = {"lr": lr, "scaler": scaler, "xgb": xgb}
    return base64.b64encode(pickle.dumps(blob)).decode('utf-8')


def deserialize_model(s):
    return pickle.loads(base64.b64decode(s))


def run_full_training():
    """下载全部联赛数据 → 训练 → 返回 (lr, scaler, xgb, metrics)"""
    all_dfs = []
    progress_ph = st.empty()
    total = len(LEAGUE_CODE_MAP)
    for i, league in enumerate(LEAGUE_CODE_MAP.keys()):
        progress_ph.info(f"[{i+1}/{total}] 下载 {league}...")
        df = download_league_csv(league)
        if df is None:
            continue
        clean, feat_cols = preprocess_df(df)
        if clean is not None:
            all_dfs.append(clean)
    progress_ph.empty()

    if not all_dfs:
        return None, None

    combined = pd.concat(all_dfs, ignore_index=True)
    lr, scaler, xgb, metrics = train_models(combined, feat_cols)
    return (lr, scaler, xgb), metrics


def predict_with_model(model_tuple, odds):
    """用真模型预测，返回 (lr_probs, xgb_probs) 各三个概率"""
    lr, scaler, xgb = model_tuple
    h, d, a = odds
    inv = np.array([1/h, 1/d, 1/a])
    probs = inv / inv.sum()
    # 无收盘赔率，用同一值，drift=0
    features = np.array([[
        probs[0], probs[1], probs[2],
        probs[0], probs[1], probs[2],
        0.0, 0.0
    ]])
    lr_p = lr.predict_proba(scaler.transform(features))[0]
    xgb_p = xgb.predict_proba(features)[0]
    return lr_p, xgb_p


# ============ 通用工具 ============
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
if "model_loaded" not in st.session_state:
    st.session_state["model_loaded"] = False
    # 尝试从数据库加载
    try:
        loaded = load_model_from_db()
        if loaded:
            st.session_state["model_tuple"] = loaded["model"]
            st.session_state["model_meta"] = {
                "trained_at": loaded["trained_at"],
                "samples": loaded["samples"],
                "lr_logloss": loaded["lr_logloss"],
                "xgb_logloss": loaded["xgb_logloss"],
            }
            st.session_state["model_loaded"] = True
    except Exception:
        pass


POSITION_CN = {"Goalkeeper": "门将", "Defender": "后卫", "Midfielder": "中场",
               "Attacker": "前锋", "Forward": "前锋"}


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
        mw, mkw, cn, cat = LEAGUE_MAP[league_id]
        return mw, mkw, cn, cat
    return 0.55, 0.45, league_name_from_api or "未知联赛", "普通"


def parse_match(m):
    m = m.replace("vs", " ").replace("VS", " ").replace("对", " ").strip()
    sorted_teams = sorted(CN_TEAM_MAP.keys(), key=len, reverse=True)
    used_ranges, matches = [], []
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
    for cand in candidates:
        try:
            r = requests.get(f"{BASE_URL}/teams", headers=HEADERS,
                             params={"search": cand}, timeout=10)
            data = r.json()
            if not data.get("response"):
                continue
            cl = cand.lower()
            best, bs = None, -1
            for item in data["response"]:
                t = item["team"]
                tn = (t.get("name") or "").lower()
                score = 1000 if tn == cl else (
                    100 + len(cl) if tn.startswith(cl) else (
                        50 * len(cl) / max(len(tn), 1) if cl in tn else (
                            40 * len(tn) / max(len(cl), 1) if tn in cl else 0)))
                if score > bs:
                    bs, best = score, t
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
def get_asian_handicap(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/odds", headers=HEADERS,
                         params={"fixture": fixture_id, "bookmaker": 2}, timeout=10)
        data = r.json()
        if data.get("response"):
            for bm in data["response"][0].get("bookmakers", []):
                for bet in bm.get("bets", []):
                    if bet["id"] == 4:
                        vals = bet["values"]
                        for v in vals:
                            val_str = v.get("value", "")
                            m = re.search(r'Home\s+([+-]?\d+(?:\.\d+)?)', val_str)
                            if m:
                                handicap = float(m.group(1))
                                home_odd = float(v.get("odd", 0)) or None
                                away_str2 = val_str.replace("Home", "Away").replace(str(handicap), str(-handicap))
                                away_odd = None
                                for v2 in vals:
                                    if v2.get("value", "") == away_str2:
                                        away_odd = float(v2.get("odd", 0)) or None
                                        break
                                if home_odd:
                                    return handicap, home_odd, away_odd
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
            rec = data["response"][0]
            return rec.get("start", "未知") or "未知", rec.get("end", "未知") or "未知"
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
            sl = data["response"][0].get("statistics", [])
            if sl:
                best = max(sl, key=lambda s: s["games"].get("minutes") or 0)
                g = best.get("games", {})
                return {"position": g.get("position", "") or "",
                        "minutes": g.get("minutes") or 0,
                        "appearences": g.get("appearences") or 0}
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
    hs, as_ = 0, 0
    for inj in injuries:
        t_id = inj["team"]["id"]
        pos = inj["player"].get("position", "Midfielder")
        w = pos_w.get(pos, 1.0)
        if t_id == home_id:
            hs += w
        elif t_id == away_id:
            as_ += w
    return round(np.tanh((as_ - hs) / 3.0), 2), hs, as_


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


def calc_form_diff(hr, ar, hid, aid):
    return round(np.tanh((calc_form_coef(hr, hid) - calc_form_coef(ar, aid)) / 9.0), 2)


def devig(odds):
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [i / s for i in inv]


def softmax3(base, adjust):
    logits = np.array([np.log(p) for p in base]) + np.array([adjust, -adjust * 0.3, -adjust * 0.7])
    e = np.exp(logits - np.max(logits))
    return e / e.sum()


def calc_all_probs(odds, coefs, league_id, params, league_name=""):
    """五层概率：优先用真模型，无模型时用公式"""
    weights = params["weights"]
    mf = params["model_fusion"]
    override = params.get("market_fusion_override")

    market_p = np.array(devig(odds))
    adjust = sum(coefs[k] * weights[k] for k in weights)

    model_used = "公式"
    # 尝试用真模型
    if st.session_state.get("model_loaded") and st.session_state.get("model_tuple"):
        try:
            lr_p, xgb_p = predict_with_model(st.session_state["model_tuple"], odds)
            lr_p = np.array(lr_p)
            xgb_p = np.array(xgb_p)
            model_used = "真模型"
        except Exception:
            lr_p = softmax3(market_p, adjust * 0.5)
            xgb_p = softmax3(market_p, adjust * 1.0)
    else:
        lr_p = softmax3(market_p, adjust * 0.5)
        xgb_p = softmax3(market_p, adjust * 1.0)

    model_p = mf["lr"] * lr_p + mf["xgb"] * xgb_p

    # 叠加五项系数调整（在市场概率基础上）
    model_p = model_p * np.array([1 + adjust * 0.15, 1 - adjust * 0.05, 1 - adjust * 0.1])
    model_p = model_p / model_p.sum()

    if override is not None:
        mw, mkw = override, 1 - override
        _, _, cn, _ = get_league_info(league_id, league_name)
    else:
        mw, mkw, cn, _ = get_league_info(league_id, league_name)

    final_p = mw * model_p + mkw * market_p
    final_p = final_p / final_p.sum()
    return {
        "lr": (lr_p * 100).round(1), "xgb": (xgb_p * 100).round(1),
        "model": (model_p * 100).round(1), "market": (market_p * 100).round(1),
        "final": (final_p * 100).round(1),
        "league_cn": cn, "model_w": mw, "market_w": mkw,
        "model_source": model_used,
    }


def fit_poisson_lambdas(p_h, p_d, p_a, max_goals=10):
    def loss(params):
        lh, la = params
        if lh <= 0.05 or la <= 0.05 or lh > 6 or la > 6:
            return 999
        ph = pd_ = pa = 0.0
        for i in range(max_goals):
            for j in range(max_goals):
                prob = poisson.pmf(i, lh) * poisson.pmf(j, la)
                if i > j:
                    ph += prob
                elif i == j:
                    pd_ += prob
                else:
                    pa += prob
        return (ph - p_h) ** 2 + (pd_ - p_d) ** 2 + (pa - p_a) ** 2
    result = minimize(loss, [1.4, 1.1], method="Nelder-Mead",
                      options={"xatol": 1e-4, "fatol": 1e-6, "maxiter": 200})
    return float(result.x[0]), float(result.x[1])


def calc_handicap_probs(lh, la, handicap, max_goals=12):
    ph = pd_ = pa = 0.0
    for i in range(max_goals):
        for j in range(max_goals):
            prob = poisson.pmf(i, lh) * poisson.pmf(j, la)
            diff = i + handicap - j
            if diff > 0:
                ph += prob
            elif abs(diff) < 0.01:
                pd_ += prob
            else:
                pa += prob
    t = ph + pd_ + pa
    if t <= 0:
        return 0, 0, 0
    return round(ph / t * 100, 1), round(pd_ / t * 100, 1), round(pa / t * 100, 1)


def check_data_health(injuries, h2h, h_recent, a_recent, odds):
    checks = []
    checks.append(("✅", "赔率数据", "完整") if odds and odds[0] else ("❌", "赔率数据", "缺失"))
    checks.append(("✅", "伤停数据", f"{len(injuries)}条") if injuries else ("⚠️", "伤停数据", "无记录"))
    checks.append(("✅", "历史交战", f"近{len(h2h)}次") if h2h else ("⚠️", "历史交战", "无记录"))
    checks.append(("✅", "近期状态", "完整") if h_recent and a_recent else ("⚠️", "近期状态", "缺失"))
    score = sum(1 for c in checks if c[0] == "✅") / len(checks) * 100
    return checks, round(score)


def analyze_match(home_name, away_name, date_hint=None):
    hid, hs = search_team(home_name)
    aid, as_ = search_team(away_name)
    if not hid or not aid:
        return None, f"球队搜索失败：{home_name} / {away_name}"

    fixture = None
    if date_hint:
        fixture = get_fixture(hid, aid, date_hint)
        if not fixture:
            try:
                bd = datetime.strptime(date_hint, "%Y-%m-%d")
                for off in [-1, 1, -2, 2, 3]:
                    d = (bd + timedelta(days=off)).strftime("%Y-%m-%d")
                    fixture = get_fixture(hid, aid, d)
                    if fixture:
                        break
            except Exception:
                pass
    else:
        for off in range(0, 4):
            d = (datetime.now() + timedelta(days=off)).strftime("%Y-%m-%d")
            fixture = get_fixture(hid, aid, d)
            if fixture:
                break

    if not fixture:
        return None, f"未找到比赛：{hs} vs {as_}"

    fid = fixture["fixture"]["id"]
    lid = fixture["league"]["id"]
    lname = fixture["league"]["name"]
    lcountry = fixture["league"].get("country", "")

    odds = get_odds(fid)
    if not odds[0]:
        return None, f"未找到赔率：{hs} vs {as_}"

    injuries = get_injuries(fid)
    h2h = get_h2h(hid, aid)
    hr = get_recent_form(hid)
    ar = get_recent_form(aid)
    handicap, ah_h, ah_a = get_asian_handicap(fid)

    inj_coef, _, _ = calc_injury_coef(injuries, hid, aid)
    h2h_coef = calc_h2h_coef(h2h, hid)
    form_coef = calc_form_diff(hr, ar, hid, aid)
    coefs = {"injury": inj_coef, "home_away": 0.3, "h2h": h2h_coef, "form": form_coef, "motivation": 0.0}

    health, hscore = check_data_health(injuries, h2h, hr, ar, odds)
    hcn = en_to_cn(hs)
    acn = en_to_cn(as_)

    inj_list = []
    for inj in injuries:
        t_id = inj["team"]["id"]
        team_cn = hcn if t_id == hid else (acn if t_id == aid else "未知")
        pid = inj["player"].get("id")
        stats = get_player_stats(pid) if pid else {"position": "", "minutes": 0, "appearences": 0}
        raw_pos = inj["player"].get("position", "") or stats["position"]
        sd, ed = get_sidelined(pid) if pid else ("未知", "未知")
        inj_list.append({
            "球队": team_cn,
            "球员": translate_player(inj["player"].get("name", "")),
            "位置": translate_position(raw_pos),
            "角色": classify_role(stats["minutes"], stats["appearences"]),
            "原因": translate_injury_reason(inj["player"].get("reason", inj.get("type", ""))),
            "起始日期": sd,
            "预计复出": ed,
        })

    h2h_list = [{"日期": m["fixture"]["date"][:10],
                 "主队": en_to_cn(m["teams"]["home"]["name"]),
                 "比分": f"{m['goals']['home']}-{m['goals']['away']}",
                 "客队": en_to_cn(m["teams"]["away"]["name"])} for m in h2h[:5]]

    def fmt_recent(recent, team_id):
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
        "match": f"{hcn} vs {acn}",
        "league_api": lname, "league_country": lcountry, "league_id": lid,
        "odds": odds, "coefs": coefs,
        "handicap": handicap, "ah_home_odd": ah_h, "ah_away_odd": ah_a,
        "injuries": inj_list, "h2h": h2h_list,
        "home_recent": fmt_recent(hr, hid),
        "away_recent": fmt_recent(ar, aid),
        "health": health, "health_score": hscore,
        "home_cn": hcn, "away_cn": acn,
    }, None


# ================================================================
# ============ 界面 ============
# ================================================================
tab1, tab2, tab3 = st.tabs(["📊 分析", "⚙️ 调参/模型", "📚 历史记录"])

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
                fx = search_fixtures_by_date(search_date.strftime("%Y-%m-%d"))
                st.session_state["date_fixtures"] = fx
                st.session_state["date_fixtures_date"] = search_date.strftime("%Y-%m-%d")

    if "date_fixtures" in st.session_state:
        fixtures = st.session_state["date_fixtures"]
        if not fixtures:
            st.warning(f"未找到 {st.session_state.get('date_fixtures_date', '')} 当天支持的联赛比赛")
        else:
            st.success(f"共找到 {len(fixtures)} 场支持的联赛比赛")
            options, o2m = [], {}
            for f in fixtures:
                hc, ac = en_to_cn(f["teams"]["home"]["name"]), en_to_cn(f["teams"]["away"]["name"])
                lc = LEAGUE_MAP[f["league"]["id"]][2]
                ts = f["fixture"]["date"][11:16]
                opt = f"[{lc}] {hc} vs {ac} ({ts})"
                options.append(opt)
                _d = st.session_state.get("date_fixtures_date", datetime.now().strftime("%Y-%m-%d"))
                o2m[opt] = f"{hc} {ac}@{_d}"
            sel = st.multiselect("勾选要分析的比赛", options)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ 加入分析列表"):
                    if "selected_matches" not in st.session_state:
                        st.session_state["selected_matches"] = []
                    added = 0
                    for opt in sel:
                        ms = o2m.get(opt)
                        if ms and ms not in st.session_state["selected_matches"]:
                            st.session_state["selected_matches"].append(ms)
                            added += 1
                    st.success(f"成功加入 {added} 场")
                    st.rerun()
            with c2:
                if st.button("🗑️ 清空已加入"):
                    st.session_state["selected_matches"] = []
                    st.rerun()
            if st.session_state.get("selected_matches"):
                st.info(f"📋 当前待分析列表：{len(st.session_state['selected_matches'])} 场")

    st.markdown("---")
    st.subheader("📊 手动输入或确认分析列表")
    mi = st.text_input("自由格式，用逗号分隔（例如：阿森纳 切尔西, 皇马 巴萨）", "")

    cb1, cb2 = st.columns([3, 1])
    with cb1:
        do = st.button("🚀 开始批量分析", type="primary")
    with cb2:
        if st.button("🔄 强制刷新"):
            st.cache_data.clear()
            st.session_state["cache_time"] = None
            st.success("缓存已清")

    if do:
        all_m = []
        if mi:
            all_m.extend([x.strip() for x in mi.split(",") if x.strip()])
        if st.session_state.get("selected_matches"):
            all_m.extend(st.session_state["selected_matches"])
        all_m = list(dict.fromkeys(all_m))

        if not all_m:
            st.warning("请输入比赛")
        elif not api_key:
            st.error("API Key 未配置")
        else:
            results = []
            prog = st.progress(0)
            for i, m in enumerate(all_m):
                prog.progress((i + 1) / len(all_m), text=f"分析中：{m}")
                if "@" in m:
                    mp, dp = m.rsplit("@", 1)
                else:
                    mp, dp = m, None
                h, a = parse_match(mp)
                if not h or not a:
                    st.warning(f"无法解析：{m}")
                    continue
                r, err = analyze_match(h, a, dp)
                if err:
                    st.warning(err)
                else:
                    results.append(r)
            prog.empty()

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
                src = p.get("model_source", "公式")
                st.markdown(f"### {r['match']}")
                st.caption(f"🏆 {p['league_cn']} | 概率来源：{src} → 模型{int(p['model_w']*100)}% / 市场{int(p['market_w']*100)}%")
                if r["handicap"] is not None:
                    st.caption(f"🎯 亚盘：主 {r['handicap']:+.2f}（赔率 {r['ah_home_odd']}）")
                c1, c2, c3 = st.columns(3)
                c1.metric("主胜", f"{p['final'][0]}%")
                c2.metric("平局", f"{p['final'][1]}%")
                c3.metric("客胜", f"{p['final'][2]}%")
                if r["handicap"] is not None:
                    with st.container(border=True):
                        st.markdown("**🎯 让球胜平负**")
                        mp = devig(r["odds"])
                        lh, la = fit_poisson_lambdas(mp[0], mp[1], mp[2])
                        hw, hd, hl = calc_handicap_probs(lh, la, r["handicap"])
                        cc1, cc2, cc3 = st.columns(3)
                        cc1.metric(f"让球主胜 ({r['handicap']:+.2f})", f"{hw}%")
                        cc2.metric("走水", f"{hd}%")
                        cc3.metric(f"让球客胜 ({-r['handicap']:+.2f})", f"{hl}%")
                        st.caption(f"泊松 λ：主 {lh:.2f} / 客 {la:.2f}")
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
        cands = []
        for r in st.session_state["results"]:
            p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], params, r["league_api"])
            pf = p["final"]
            mxi = int(np.argmax(pf))
            if pf[mxi] > 60 and 1.30 <= r["odds"][mxi] <= 2.50 and r["health_score"] >= 80:
                cands.append({"match": r["match"], "league": p["league_cn"],
                              "pick": ["主胜", "平局", "客胜"][mxi] + "（胜平负）",
                              "prob": float(pf[mxi]), "odd": r["odds"][mxi], "health": r["health_score"]})
            if r["handicap"] is not None and r["ah_home_odd"]:
                mp = devig(r["odds"])
                lh, la = fit_poisson_lambdas(mp[0], mp[1], mp[2])
                hw, hd, hl = calc_handicap_probs(lh, la, r["handicap"])
                if hw > hl and hw > 62 and 1.30 <= r["ah_home_odd"] <= 2.50:
                    cands.append({"match": r["match"], "league": p["league_cn"],
                                  "pick": f"让球主胜 ({r['handicap']:+.2f})",
                                  "prob": hw, "odd": r["ah_home_odd"], "health": r["health_score"]})
                elif hl > hw and hl > 62 and r["ah_away_odd"] and 1.30 <= r["ah_away_odd"] <= 2.50:
                    cands.append({"match": r["match"], "league": p["league_cn"],
                                  "pick": f"让球客胜 ({-r['handicap']:+.2f})",
                                  "prob": hl, "odd": r["ah_away_odd"], "health": r["health_score"]})
        best, bs = None, 0
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                c1, c2 = cands[i], cands[j]
                if c1["match"] == c2["match"]:
                    continue
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
                st.markdown(f"**{c1['pick']}** | 概率 {c1['prob']}% | 赔率 {c1['odd']}")
            with col2:
                st.markdown(f"**🥈 {c2['match']}**")
                st.markdown(f"**{c2['pick']}** | 概率 {c2['prob']}% | 赔率 {c2['odd']}")
            st.markdown(f"**组合赔率 {to:.2f}**")
        else:
            st.warning("⚠️ 今日无符合条件的二串一推荐")

with tab2:
    st.subheader("🤖 模型训练")
    if st.session_state.get("model_loaded") and st.session_state.get("model_meta"):
        meta = st.session_state["model_meta"]
        st.success(f"✅ 模型已加载 · 训练于 {meta.get('trained_at')}")
        c1, c2, c3 = st.columns(3)
        c1.metric("训练样本", f"{meta.get('samples', 0):,} 场")
        c2.metric("LR LogLoss", f"{meta.get('lr_logloss', 0):.4f}")
        c3.metric("XGB LogLoss", f"{meta.get('xgb_logloss', 0):.4f}")
    else:
        st.warning("⚠️ 尚未加载模型。当前分析使用'公式模式'（市场概率 + 五项系数）。")
        st.caption("点击下方【🚀 一键学习】拉取 football-data.co.uk 历史数据训练真模型。")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚀 一键学习", type="primary"):
            with st.spinner("正在下载历史数据并训练模型，大约需要 1-3 分钟..."):
                try:
                    result, metrics = run_full_training()
                    if result is None:
                        st.error("训练失败：未能下载到任何历史数据")
                    else:
                        blob = serialize_model(*result)
                        save_model_to_db(blob, metrics)
                        st.session_state["model_tuple"] = result
                        st.session_state["model_meta"] = {
                            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "samples": metrics["samples"],
                            "lr_logloss": metrics["lr_logloss"],
                            "xgb_logloss": metrics["xgb_logloss"],
                        }
                        st.session_state["model_loaded"] = True
                        st.success(f"✅ 训练完成！样本 {metrics['samples']:,} 场，LR LogLoss {metrics['lr_logloss']:.4f}，XGB LogLoss {metrics['xgb_logloss']:.4f}")
                        st.rerun()
                except Exception as e:
                    st.error(f"训练出错：{e}")
    with col_b:
        if st.button("🗑️ 清除当前模型"):
            st.session_state["model_loaded"] = False
            st.session_state["model_tuple"] = None
            st.session_state["model_meta"] = None
            engine = get_db_engine()
            if engine:
                try:
                    from sqlalchemy import text
                    with engine.connect() as conn:
                        conn.execute(text("DELETE FROM model_storage"))
                        conn.commit()
                except Exception:
                    pass
            st.success("已清除")
            st.rerun()

    st.markdown("---")
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
            st.warning(f"⚠️ 合计 {tw:.2f}")
        else:
            st.success(f"✅ 合计 {tw:.2f}")

    st.markdown("**② 模型融合比例**")
    params_now["model_fusion"]["lr"] = st.slider("LR", 0.0, 1.0, params_now["model_fusion"]["lr"], 0.01)
    params_now["model_fusion"]["xgb"] = round(1 - params_now["model_fusion"]["lr"], 2)
    st.caption(f"XGB = {params_now['model_fusion']['xgb']}")

    st.markdown("**③ 全局融合覆盖（可选）**")
    use_ovr = st.checkbox("启用（忽略联赛默认）", value=params_now.get("market_fusion_override") is not None)
    if use_ovr:
        ov = st.slider("全局模型权重", 0.0, 1.0, params_now.get("market_fusion_override") or 0.55, 0.01)
        params_now["market_fusion_override"] = ov
    else:
        params_now["market_fusion_override"] = None

    st.session_state["params"] = params_now

    ca, cb = st.columns(2)
    with ca:
        if st.button("💾 保存为基准"):
            st.session_state["param_versions"].append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "params": copy.deepcopy(params_now),
            })
            st.success("已保存")
    with cb:
        if st.button("↩️ 恢复默认"):
            st.session_state["params"] = get_default_params()
            st.rerun()

    if st.session_state.get("param_versions"):
        with st.expander("📋 历史版本"):
            for i, v in enumerate(reversed(st.session_state["param_versions"])):
                st.markdown(f"**版本 {len(st.session_state['param_versions'])-i}** · {v['time']}")
                st.caption(f"伤停{v['params']['weights']['injury']} 主客{v['params']['weights']['home_away']} H2H{v['params']['weights']['h2h']} 状态{v['params']['weights']['form']} 战意{v['params']['weights']['motivation']}")

with tab3:
    st.subheader("📚 历史分析记录")
    if "auto_checked_tab3" not in st.session_state:
        st.session_state["auto_checked_tab3"] = True
        try:
            with st.spinner("正在检查赛果..."):
                _n = auto_update_results()
            if _n > 0:
                st.success(f"✅ 已自动回填 {_n} 场比赛赛果")
        except Exception:
            pass

    ca, cb = st.columns([1, 4])
    with ca:
        if st.button("🔄 手动检查赛果"):
            with st.spinner("正在查询..."):
                n = auto_update_results()
                st.success(f"已更新 {n} 场")
                st.rerun()
    history = load_history(200)
    if not history:
        st.info("暂无历史记录")
    else:
        st.success(f"共 {len(history)} 条")
        fin = [h for h in history if h.get("actual_result")]
        if fin:
            hits = 0
            for h in fin:
                try:
                    pj = json.loads(h.get("probs_json") or "{}")
                    f = pj.get("final", [])
                    if isinstance(f, list) and len(f) == 3:
                        pred = ["主胜", "平局", "客胜"][int(np.argmax(f))]
                        if pred == h["actual_result"]:
                            hits += 1
                except Exception:
                    pass
            rate = hits / len(fin) * 100
            st.metric("模型命中率", f"{rate:.1f}%", f"已回填 {len(fin)} 场")
        for h in history:
            with st.container(border=True):
                st.markdown(f"**{h.get('match_name','')}** · {h.get('league','')}")
                st.caption(f"分析时间：{h.get('analysis_time','')} | 健康度：{h.get('health_score',0)}%")
                try:
                    pj = json.loads(h.get("probs_json") or "{}")
                    f = pj.get("final")
                    if isinstance(f, list) and len(f) == 3:
                        st.markdown(f"最终概率：主 **{f[0]}%** / 平 **{f[1]}%** / 客 **{f[2]}%**")
                except Exception:
                    pass
                st.markdown(f"赔率：主 {h.get('home_odds')} / 平 {h.get('draw_odds')} / 客 {h.get('away_odds')}")
                if h.get("actual_result"):
                    st.success(f"✅ 赛果：{h['actual_result']}")
                else:
                    st.info("⏳ 赛果待更新")
                    with st.expander("手动回填（可选）"):
                        cx, cy = st.columns([3, 1])
                        with cx:
                            res = st.selectbox("选择赛果", ["", "主胜", "平局", "客胜"], key=f"res_{h['id']}")
                        with cy:
                            if st.button("保存", key=f"sv_{h['id']}"):
                                if res:
                                    update_result(h["id"], res)
                                    st.success("已保存")
                                    st.rerun()
