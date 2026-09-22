# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import requests
import numpy as np
import copy
import json
import pickle
import base64
import io
from datetime import datetime, timedelta
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss
from xgboost import XGBClassifier
from teams_cn import CN_TEAM_MAP, EN_TO_CN, cn_to_en, en_to_cn, translate_injury_reason
from city_coords import get_travel_km
from extended_features import (calc_schedule_density, calc_travel_factor,
    calc_eu_pressure, is_eu_match, get_team_league, LEAGUE_TIER)

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="⚽")
st.title("⚽ 足球分析模型 - 完整版")

api_key = os.environ.get("API_FOOTBALL_KEY", "")
db_url = os.environ.get("DB_URL", "")
HEADERS = {"x-apisports-key": api_key}
BASE_URL = "https://v3.football.api-sports.io"

LEAGUE_CODE_MAP = {"英超": "E0", "英冠": "E1", "西甲": "SP1", "西乙": "SP2",
    "德甲": "D1", "德乙": "D2", "意甲": "I1", "意乙": "I2",
    "法甲": "F1", "法乙": "F2", "荷甲": "N1", "葡超": "P1",
    "比甲": "B1", "苏超": "SC0", "挪超": "NOR", "瑞超": "SWE",
    "丹超": "DNK", "芬超": "FIN"}
TRAINING_SEASONS = ["2223", "2324", "2425"]
YELLOW_THRESHOLD = {"英超": 5, "英冠": 5, "西甲": 5, "西乙": 5,
    "德甲": 5, "德乙": 5, "意甲": 5, "意乙": 5,
    "法甲": 3, "法乙": 3, "荷甲": 5, "葡超": 5,
    "比甲": 5, "苏超": 6, "挪超": 4, "瑞超": 3, "丹超": 4, "芬超": 4}
SUPPORTED_LEAGUES = ["英超", "西甲", "德甲", "意甲", "法甲",
    "欧冠", "欧联", "欧协联", "英冠", "德乙", "西乙", "法乙",
    "荷甲", "葡超", "比甲", "苏超", "挪超", "瑞超", "丹超", "芬超"]


def get_db_engine():
    if not db_url or not db_url.startswith("postgresql"): return None
    try:
        from sqlalchemy import create_engine
        return create_engine(db_url)
    except Exception:
        return None


def save_to_db(record):
    engine = get_db_engine()
    if not engine: return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""INSERT INTO analysis_history 
                (match_id, match_name, league, analysis_time, home_odds, draw_odds, away_odds, 
                 coefs_json, probs_json, health_score)
                VALUES (:mid, :mn, :lg, :at, :ho, :do, :ao, :cj, :pj, :hs)"""), record)
            conn.commit()
        return True
    except Exception:
        return False


def load_history(limit=200):
    engine = get_db_engine()
    if not engine: return []
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM analysis_history ORDER BY created_at DESC LIMIT :lim"), {"lim": limit})
            return [dict(r._mapping) for r in result]
    except Exception:
        return []


def update_result(record_id, actual_result):
    engine = get_db_engine()
    if not engine: return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("UPDATE analysis_history SET actual_result = :ar WHERE id = :id"), {"ar": actual_result, "id": record_id})
            conn.commit()
        return True
    except Exception:
        return False


def auto_update_results():
    engine = get_db_engine()
    if not engine: return 0
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""SELECT id, match_id FROM analysis_history
                WHERE (actual_result IS NULL OR actual_result = '')
                AND match_id IS NOT NULL
                AND created_at > NOW() - INTERVAL '30 days'"""))
            rows = [(r[0], r[1]) for r in result]
    except Exception:
        return 0
    if not rows: return 0
    updated = 0
    for rid, mid in rows:
        try:
            r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params={"id": mid}, timeout=10)
            data = r.json()
            if not data.get("response"): continue
            fx = data["response"][0]
            status = fx["fixture"]["status"]["short"]
            if status in ["FT", "AET", "PEN"]:
                hg, ag = fx["goals"]["home"], fx["goals"]["away"]
                if hg is None or ag is None: continue
                result = "主胜" if hg > ag else ("平局" if hg == ag else "客胜")
                if update_result(rid, result): updated += 1
        except Exception:
            continue
    return updated


def calc_calibration():
    try:
        history = load_history(1000)
        finished = [h for h in history if h.get("actual_result")]
        if len(finished) < 10: return None
        bins_home = [[] for _ in range(10)]
        for h in finished:
            try:
                pj = json.loads(h.get("probs_json") or "{}")
                fin = pj.get("final", [])
                if not isinstance(fin, list) or len(fin) != 3: continue
                p_home = float(fin[0])
                bin_idx = min(int(p_home // 10), 9)
                bins_home[bin_idx].append((p_home, h["actual_result"] == "主胜"))
            except Exception:
                continue
        rows = []
        for i in range(10):
            samples = bins_home[i]
            if len(samples) < 3: continue
            avg_pred = sum(s[0] for s in samples) / len(samples)
            actual_rate = sum(1 for s in samples if s[1]) / len(samples) * 100
            rows.append({"概率区间": f"{i*10}-{(i+1)*10}%", "样本数": len(samples),
                "预测均值": round(avg_pred, 1), "实际主胜率": round(actual_rate, 1),
                "偏差": round(actual_rate - avg_pred, 1)})
        return rows
    except Exception:
        return None


def calc_overall_logloss():
    try:
        history = load_history(1000)
        finished = [h for h in history if h.get("actual_result")]
        if not finished: return None
        result_map = {"主胜": 0, "平局": 1, "客胜": 2}
        losses = []
        for h in finished:
            try:
                pj = json.loads(h.get("probs_json") or "{}")
                fin = pj.get("final", [])
                if not isinstance(fin, list) or len(fin) != 3: continue
                p = [max(float(x) / 100, 1e-6) for x in fin]
                y = result_map[h["actual_result"]]
                losses.append(-np.log(p[y]))
            except Exception:
                continue
        if not losses: return None
        return round(float(np.mean(losses)), 4), len(losses)
    except Exception:
        return None


def save_training_log(metrics):
    engine = get_db_engine()
    if not engine: return
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""INSERT INTO training_log 
                (trained_at, samples, lr_logloss, xgb_logloss, notes)
                VALUES (NOW(), :s, :lr, :xgb, :n)"""), {
                "s": metrics.get("samples", 0), "lr": metrics.get("lr_logloss", 0),
                "xgb": metrics.get("xgb_logloss", 0), "n": metrics.get("notes", "")})
            conn.commit()
    except Exception:
        pass


def load_training_logs(limit=30):
    engine = get_db_engine()
    if not engine: return []
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""SELECT trained_at, samples, lr_logloss, xgb_logloss, notes 
                FROM training_log ORDER BY trained_at DESC LIMIT :lim"""), {"lim": limit})
            return [dict(r._mapping) for r in result]
    except Exception:
        return []


def save_model_to_db(blob_base64, metrics):
    engine = get_db_engine()
    if not engine: return False
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM model_storage"))
            conn.execute(text("""INSERT INTO model_storage 
                (model_blob, samples, lr_logloss, xgb_logloss, notes)
                VALUES (:b, :s, :lr, :xgb, :n)"""), {
                "b": blob_base64, "s": metrics.get("samples", 0),
                "lr": metrics.get("lr_logloss", 0), "xgb": metrics.get("xgb_logloss", 0),
                "n": metrics.get("notes", "")})
            conn.commit()
        return True
    except Exception:
        return False


def load_model_from_db():
    engine = get_db_engine()
    if not engine: return None
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("""SELECT model_blob, trained_at, samples, lr_logloss, xgb_logloss 
                FROM model_storage ORDER BY id DESC LIMIT 1"""))
            row = result.fetchone()
            if not row: return None
            return {"model": deserialize_model(row[0]), "trained_at": str(row[1]),
                "samples": row[2], "lr_logloss": row[3], "xgb_logloss": row[4]}
    except Exception:
        return None


def download_league_csv(league_cn, seasons=TRAINING_SEASONS):
    code = LEAGUE_CODE_MAP.get(league_cn)
    if not code: return None
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
    if not dfs: return None
    return pd.concat(dfs, ignore_index=True)


def preprocess_df(df):
    needed = ['B365H', 'B365D', 'B365A', 'FTHG', 'FTAG']
    for c in needed:
        if c not in df.columns: return None, None
    for col in ['B365H', 'B365D', 'B365A', 'FTHG', 'FTAG', 'B365CH', 'B365CD', 'B365CA']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=needed).copy()
    if len(df) < 30: return None, None
    odds = df[['B365H', 'B365D', 'B365A']].values.astype(float)
    inv = 1.0 / odds
    probs = inv / inv.sum(axis=1, keepdims=True)
    df['p_home'] = probs[:, 0]
    df['p_draw'] = probs[:, 1]
    df['p_away'] = probs[:, 2]
    if all(c in df.columns for c in ['B365CH', 'B365CD', 'B365CA']):
        df_ch = df.dropna(subset=['B365CH', 'B365CD', 'B365CA']).copy()
        df['p_home_close'] = df['p_home']
        df['p_draw_close'] = df['p_draw']
        df['p_away_close'] = df['p_away']
        df['drift_home'] = 0.0
        df['drift_away'] = 0.0
        if len(df_ch) > 0:
            odds_c = df_ch[['B365CH', 'B365CD', 'B365CA']].values.astype(float)
            inv_c = 1.0 / odds_c
            probs_c = inv_c / inv_c.sum(axis=1, keepdims=True)
            df.loc[df_ch.index, 'p_home_close'] = probs_c[:, 0]
            df.loc[df_ch.index, 'p_draw_close'] = probs_c[:, 1]
            df.loc[df_ch.index, 'p_away_close'] = probs_c[:, 2]
            df.loc[df_ch.index, 'drift_home'] = probs_c[:, 0] - df.loc[df_ch.index, 'p_home']
            df.loc[df_ch.index, 'drift_away'] = probs_c[:, 2] - df.loc[df_ch.index, 'p_away']
    else:
        df['p_home_close'] = df['p_home']
        df['p_draw_close'] = df['p_draw']
        df['p_away_close'] = df['p_away']
        df['drift_home'] = 0.0
        df['drift_away'] = 0.0
    df['result'] = df.apply(lambda r: 0 if r['FTHG'] > r['FTAG'] else (1 if r['FTHG'] == r['FTAG'] else 2), axis=1)
    feature_cols = ['p_home', 'p_draw', 'p_away', 'p_home_close', 'p_draw_close', 'p_away_close',
        'drift_home', 'drift_away']
    return df, feature_cols


def train_models(df, feature_cols):
    X = df[feature_cols].values
    y = df['result'].values
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)
    lr = LogisticRegression(multi_class='multinomial', solver='lbfgs', max_iter=1000, class_weight='balanced')
    lr.fit(X_train_s, y_train)
    xgb = XGBClassifier(objective='multi:softprob', num_class=3, n_estimators=200, max_depth=4,
        learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
        eval_metric='mlogloss', verbosity=0, use_label_encoder=False)
    xgb.fit(X_train, y_train)
    try:
        lr_loss = float(log_loss(y_test, lr.predict_proba(X_test_s)))
        xgb_loss = float(log_loss(y_test, xgb.predict_proba(X_test)))
    except Exception:
        lr_loss, xgb_loss = 0, 0
    metrics = {"samples": len(df), "train": split, "test": len(X) - split,
        "lr_logloss": lr_loss, "xgb_logloss": xgb_loss,
        "notes": f"联赛数 {df['league_cn'].nunique()}，赛季 {df['season'].nunique()}"}
    return lr, scaler, xgb, metrics


def serialize_model(lr, scaler, xgb):
    return base64.b64encode(pickle.dumps({"lr": lr, "scaler": scaler, "xgb": xgb})).decode('utf-8')


def deserialize_model(s):
    return pickle.loads(base64.b64decode(s))


def run_full_training():
    all_dfs = []
    progress_ph = st.empty()
    total = len(LEAGUE_CODE_MAP)
    for i, league in enumerate(LEAGUE_CODE_MAP.keys()):
        progress_ph.info(f"[{i+1}/{total}] 下载 {league}...")
        df = download_league_csv(league)
        if df is None: continue
        clean, feat_cols = preprocess_df(df)
        if clean is not None: all_dfs.append(clean)
    progress_ph.empty()
    if not all_dfs: return None, None
    combined = pd.concat(all_dfs, ignore_index=True)
    lr, scaler, xgb, metrics = train_models(combined, feat_cols)
    return (lr, scaler, xgb), metrics


def predict_with_model(model_tuple, odds):
    lr, scaler, xgb = model_tuple
    h, d, a = odds
    inv = np.array([1/h, 1/d, 1/a])
    probs = inv / inv.sum()
    features = np.array([[probs[0], probs[1], probs[2], probs[0], probs[1], probs[2], 0.0, 0.0]])
    return lr.predict_proba(scaler.transform(features))[0], xgb.predict_proba(features)[0]


def current_season():
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def _base_params():
    return {"weights": {"injury": 0.20, "home_away": 0.20, "h2h": 0.18, "form": 0.21, "motivation": 0.21},
        "extended_weights": {"schedule": 0.5, "travel": 0.3, "eu_pressure": 0.5},
        "model_fusion": {"lr": 0.45, "xgb": 0.55}, "market_fusion_override": None}


def get_default_params():
    default = _base_params()
    by_league = {lg: copy.deepcopy(default) for lg in SUPPORTED_LEAGUES}
    by_league["英超"]["weights"] = {"injury": 0.22, "home_away": 0.20, "h2h": 0.15, "form": 0.22, "motivation": 0.21}
    by_league["德甲"]["weights"] = {"injury": 0.20, "home_away": 0.20, "h2h": 0.15, "form": 0.24, "motivation": 0.21}
    by_league["意甲"]["weights"] = {"injury": 0.21, "home_away": 0.19, "h2h": 0.16, "form": 0.21, "motivation": 0.23}
    by_league["西甲"]["weights"] = {"injury": 0.19, "home_away": 0.20, "h2h": 0.20, "form": 0.21, "motivation": 0.20}
    by_league["法甲"]["weights"] = {"injury": 0.21, "home_away": 0.18, "h2h": 0.17, "form": 0.22, "motivation": 0.22}
    by_league["挪超"]["weights"] = {"injury": 0.18, "home_away": 0.28, "h2h": 0.15, "form": 0.22, "motivation": 0.17}
    by_league["瑞超"]["weights"] = {"injury": 0.18, "home_away": 0.28, "h2h": 0.15, "form": 0.22, "motivation": 0.17}
    by_league["丹超"]["weights"] = {"injury": 0.19, "home_away": 0.26, "h2h": 0.15, "form": 0.22, "motivation": 0.18}
    by_league["芬超"]["weights"] = {"injury": 0.18, "home_away": 0.28, "h2h": 0.13, "form": 0.23, "motivation": 0.18}
    by_league["欧冠"]["weights"] = {"injury": 0.24, "home_away": 0.18, "h2h": 0.18, "form": 0.22, "motivation": 0.18}
    by_league["欧联"]["weights"] = {"injury": 0.22, "home_away": 0.19, "h2h": 0.18, "form": 0.23, "motivation": 0.18}
    by_league["欧协联"]["weights"] = {"injury": 0.22, "home_away": 0.19, "h2h": 0.18, "form": 0.23, "motivation": 0.18}
    by_league["欧冠"]["extended_weights"] = {"schedule": 0.6, "travel": 0.4, "eu_pressure": 0.8}
    by_league["欧联"]["extended_weights"] = {"schedule": 0.6, "travel": 0.4, "eu_pressure": 0.8}
    by_league["欧协联"]["extended_weights"] = {"schedule": 0.5, "travel": 0.4, "eu_pressure": 0.7}
    by_league["挪超"]["extended_weights"] = {"schedule": 0.5, "travel": 0.6, "eu_pressure": 0.5}
    by_league["瑞超"]["extended_weights"] = {"schedule": 0.5, "travel": 0.6, "eu_pressure": 0.5}
    by_league["芬超"]["extended_weights"] = {"schedule": 0.5, "travel": 0.7, "eu_pressure": 0.5}
    return {"default": default, "by_league": by_league}


def get_params_for_league(params, league_cn):
    if not isinstance(params, dict) or "by_league" not in params:
        return params if "weights" in params else _base_params()
    if league_cn in params["by_league"]: return params["by_league"][league_cn]
    return params["default"]


try:
    if "params" not in st.session_state:
        st.session_state["params"] = get_default_params()
    else:
        if not isinstance(st.session_state["params"], dict) or "by_league" not in st.session_state["params"]:
            st.session_state["params"] = get_default_params()
    if "param_versions" not in st.session_state: st.session_state["param_versions"] = []
    if "cache_time" not in st.session_state: st.session_state["cache_time"] = None
    if "model_loaded" not in st.session_state:
        st.session_state["model_loaded"] = False
        try:
            loaded = load_model_from_db()
            if loaded:
                st.session_state["model_tuple"] = loaded["model"]
                st.session_state["model_meta"] = {"trained_at": loaded["trained_at"],
                    "samples": loaded["samples"], "lr_logloss": loaded["lr_logloss"],
                    "xgb_logloss": loaded["xgb_logloss"]}
                st.session_state["model_loaded"] = True
        except Exception:
            pass
except Exception:
    pass


POSITION_CN = {"Goalkeeper": "门将", "Defender": "后卫", "Midfielder": "中场",
    "Attacker": "前锋", "Forward": "前锋", "G": "门将", "D": "后卫", "M": "中场", "F": "前锋"}


def translate_position(pos):
    if not pos: return "未知"
    return POSITION_CN.get(pos, pos)


PLAYER_CN_MAP = {"Erling Haaland": "哈兰德", "Kevin De Bruyne": "德布劳内", "Mohamed Salah": "萨拉赫",
    "Virgil van Dijk": "范戴克", "Bukayo Saka": "萨卡", "Martin Odegaard": "厄德高",
    "Harry Kane": "凯恩", "Son Heung-min": "孙兴慜", "Phil Foden": "福登",
    "Lionel Messi": "梅西", "Kylian Mbappe": "姆巴佩", "Vinicius Junior": "维尼修斯",
    "Jude Bellingham": "贝林厄姆", "Robert Lewandowski": "莱万", "Lamine Yamal": "亚马尔"}


def translate_player(name):
    if not name: return ""
    if name in PLAYER_CN_MAP: return f"{PLAYER_CN_MAP[name]} ({name})"
    return name


LEAGUE_MAP = {39: (0.65, 0.35, "英超", "顶级"), 140: (0.55, 0.45, "西甲", "顶级"),
    78: (0.65, 0.35, "德甲", "顶级"), 135: (0.65, 0.35, "意甲", "顶级"),
    61: (0.55, 0.45, "法甲", "顶级"), 2: (0.70, 0.30, "欧冠", "欧战"),
    3: (0.70, 0.30, "欧联", "欧战"), 848: (0.70, 0.30, "欧协联", "欧战"),
    40: (0.55, 0.45, "英冠", "普通"), 79: (0.55, 0.45, "德乙", "普通"),
    141: (0.55, 0.45, "西乙", "普通"), 62: (0.55, 0.45, "法乙", "普通"),
    88: (0.55, 0.45, "荷甲", "普通"), 94: (0.55, 0.45, "葡超", "普通"),
    144: (0.55, 0.45, "比甲", "普通"), 179: (0.55, 0.45, "苏超", "普通"),
    103: (0.55, 0.45, "挪超", "普通"), 113: (0.55, 0.45, "瑞超", "普通"),
    119: (0.55, 0.45, "丹超", "普通"), 108: (0.55, 0.45, "芬超", "普通")}


def get_league_info(league_id, league_name_from_api=""):
    if league_id in LEAGUE_MAP:
        mw, mkw, cn, cat = LEAGUE_MAP[league_id]
        return mw, mkw, cn, cat
    return 0.55, 0.45, league_name_from_api or "未知联赛", "普通"


def parse_match(m):
    if "||" in m:
        parts = m.split("||", 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()
    m = m.replace("vs", " ").replace("VS", " ").replace("对", " ").strip()
    sorted_teams = sorted(CN_TEAM_MAP.keys(), key=len, reverse=True)
    used_ranges, matches = [], []
    for cn in sorted_teams:
        start = 0
        while True:
            idx = m.find(cn, start)
            if idx == -1: break
            end = idx + len(cn)
            overlap = any(not (end <= s or idx >= e) for s, e in used_ranges)
            if not overlap:
                matches.append((idx, cn))
                used_ranges.append((idx, end))
                break
            start = idx + 1
    matches.sort()
    if len(matches) >= 2: return matches[0][1], matches[1][1]
    parts = m.split()
    if len(parts) < 2: return None, None
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
def get_fixture_by_id(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
            params={"id": fixture_id}, timeout=10)
        data = r.json()
        if data.get("response"):
            return data["response"][0]
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600)
def search_team(name):
    en_name = cn_to_en(name)
    candidates = [en_name]
    cleaned = en_name.replace("/", " ").replace("-", " ").replace(".", "").replace("  ", " ").strip()
    if cleaned != en_name: candidates.append(cleaned)
    accents = {"ø": "o", "å": "a", "æ": "ae", "ö": "o", "ä": "a", "ü": "u",
        "é": "e", "è": "e", "í": "i", "ó": "o", "á": "a", "ñ": "n", "ç": "c",
        "ş": "s", "ğ": "g", "ı": "i", "ł": "l", "ż": "z", "ź": "z", "ś": "s",
        "č": "c", "ř": "r", "ž": "z", "š": "s", "ď": "d", "ň": "n", "ě": "e",
        "ő": "o", "ű": "u", "ã": "a", "õ": "o", "â": "a", "ê": "e", "î": "i",
        "ô": "o", "û": "u", "à": "a", "ì": "i", "ò": "o", "ù": "u"}
    deacc = "".join(accents.get(c.lower(), c) for c in en_name)
    if deacc != en_name: candidates.append(deacc)
    if " " in en_name or "/" in en_name:
        first_word = en_name.replace("/", " ").split()[0]
        if first_word not in candidates: candidates.append(first_word)
    for cand in candidates:
        try:
            r = requests.get(f"{BASE_URL}/teams", headers=HEADERS, params={"search": cand}, timeout=10)
            data = r.json()
            if not data.get("response"): continue
            cl = cand.lower()
            best, bs = None, -1
            for item in data["response"]:
                t = item["team"]
                tn = (t.get("name") or "")
                tnl = tn.lower()
                exclude_keywords = [" w", "women", "feminine", "ladies", "female",
                    " u19", " u21", " u23", " ii", "youth", "academy", "reserves", "(w)"]
                if any(kw in " " + tnl + " " for kw in exclude_keywords): continue
                score = 1000 if tnl == cl else (100 + len(cl) if tnl.startswith(cl) else (
                    50 * len(cl) / max(len(tnl), 1) if cl in tnl else (
                    40 * len(tnl) / max(len(cl), 1) if tnl in cl else 0)))
                if score > bs: bs, best = score, t
            if best: return best["id"], best["name"]
        except Exception:
            continue
    return None, None


@st.cache_data(ttl=3600)
def get_odds(fixture_id):
    for bm_id in [2, 8, 10, None]:
        try:
            params = {"fixture": fixture_id}
            if bm_id is not None: params["bookmaker"] = bm_id
            r = requests.get(f"{BASE_URL}/odds", headers=HEADERS, params=params, timeout=10)
            data = r.json()
            if data.get("response"):
                for bm in data["response"][0].get("bookmakers", []):
                    for bet in bm.get("bets", []):
                        if bet["id"] == 1:
                            vals = bet["values"]
                            h = next((float(v["odd"]) for v in vals if v["value"] == "Home"), None)
                            d = next((float(v["odd"]) for v in vals if v["value"] == "Draw"), None)
                            a = next((float(v["odd"]) for v in vals if v["value"] == "Away"), None)
                            if h and d and a: return h, d, a
        except Exception:
            continue
    return None, None, None


@st.cache_data(ttl=3600)
def get_injuries(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/injuries", headers=HEADERS, params={"fixture": fixture_id}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []


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
                cards = best.get("cards", {}) or {}
                return {"position": g.get("position", "") or "", "minutes": g.get("minutes") or 0,
                    "appearences": g.get("appearences") or 0,
                    "yellow": cards.get("yellow") or 0, "yellowred": cards.get("yellowred") or 0,
                    "red": cards.get("red") or 0}
    except Exception:
        pass
    return {"position": "", "minutes": 0, "appearences": 0, "yellow": 0, "yellowred": 0, "red": 0}


def classify_role(minutes, appearances):
    if not appearances or appearances < 3 or minutes < 100: return "未知"
    if minutes >= 1500: return "主力"
    if minutes >= 600: return "轮换"
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
def get_recent_form(team_id, last=10):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
            params={"team": team_id, "last": last, "status": "FT"}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []


def get_lineups_safe(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/fixtures/lineups", headers=HEADERS,
            params={"fixture": fixture_id}, timeout=8)
        resp = r.json().get("response", [])
        return resp if isinstance(resp, list) else []
    except Exception:
        return []


def get_standings_safe(league_id):
    try:
        season = current_season()
        r = requests.get(f"{BASE_URL}/standings", headers=HEADERS,
            params={"league": league_id, "season": season}, timeout=8)
        data = r.json()
        resp = data.get("response", [])
        if not isinstance(resp, list) or not resp: return []
        league_data = resp[0].get("league", {})
        standings = league_data.get("standings", [])
        if not isinstance(standings, list) or not standings: return []
        first_group = standings[0]
        if not isinstance(first_group, list): return []
        return first_group
    except Exception:
        return []


def calc_injury_coef(injuries, home_id, away_id):
    pos_w = {"Goalkeeper": 1.2, "Defender": 1.1, "Midfielder": 1.0, "Attacker": 1.1}
    hs, as_ = 0, 0
    for inj in injuries:
        t_id = inj["team"]["id"]
        pos = inj["player"].get("position", "Midfielder")
        w = pos_w.get(pos, 1.0)
        if t_id == home_id: hs += w
        elif t_id == away_id: as_ += w
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


def calc_all_probs(odds, coefs, league_id, params, league_name="",
                   schedule_coef=0.0, travel_coef=0.0, eu_pressure=0.0):
    _, _, league_cn, _ = get_league_info(league_id, league_name)
    league_params = get_params_for_league(params, league_cn)
    weights = league_params["weights"]
    ew = league_params.get("extended_weights", {"schedule": 0.5, "travel": 0.3, "eu_pressure": 0.5})
    mf = league_params["model_fusion"]
    override = league_params.get("market_fusion_override")
    market_p = np.array(devig(odds))
    base_adjust = sum(coefs.get(k, 0) * weights[k] for k in weights)
    ext_adjust = (schedule_coef * ew.get("schedule", 0.5) + travel_coef * ew.get("travel", 0.3) +
        eu_pressure * ew.get("eu_pressure", 0.5))
    adjust = base_adjust + ext_adjust * 0.3
    model_used = "公式"
    try:
        if st.session_state.get("model_loaded") and st.session_state.get("model_tuple"):
            lr_p, xgb_p = predict_with_model(st.session_state["model_tuple"], odds)
            lr_p = np.array(lr_p)
            xgb_p = np.array(xgb_p)
            model_used = "真模型"
        else:
            lr_p = softmax3(market_p, adjust * 0.5)
            xgb_p = softmax3(market_p, adjust * 1.0)
    except Exception:
        lr_p = softmax3(market_p, adjust * 0.5)
        xgb_p = softmax3(market_p, adjust * 1.0)
    model_p = mf["lr"] * lr_p + mf["xgb"] * xgb_p
    model_p = model_p * np.array([1 + adjust * 0.15, 1 - adjust * 0.05, 1 - adjust * 0.1])
    model_p = model_p / model_p.sum()
    if override is not None:
        mw, mkw = override, 1 - override
    else:
        mw, mkw, _, _ = get_league_info(league_id, league_name)
    final_p = mw * model_p + mkw * market_p
    final_p = final_p / final_p.sum()
    return {"lr": (lr_p * 100).round(1), "xgb": (xgb_p * 100).round(1),
        "model": (model_p * 100).round(1), "market": (market_p * 100).round(1),
        "final": (final_p * 100).round(1), "league_cn": league_cn,
        "model_w": mw, "market_w": mkw, "model_source": model_used,
        "ext_adjust": round(ext_adjust, 3)}


def check_data_health(injuries, h2h, h_recent, a_recent, odds):
    checks = []
    checks.append(("✅", "赔率数据", "完整") if odds and odds[0] else ("❌", "赔率数据", "缺失"))
    checks.append(("✅", "伤停数据", f"{len(injuries)}条") if injuries else ("⚠️", "伤停数据", "无记录"))
    checks.append(("✅", "历史交战", f"近{len(h2h)}次") if h2h else ("⚠️", "历史交战", "无记录"))
    checks.append(("✅", "近期状态", "完整") if h_recent and a_recent else ("⚠️", "近期状态", "缺失"))
    score = sum(1 for c in checks if c[0] == "✅") / len(checks) * 100
    return checks, round(score)


def analyze_match(home_name, away_name, date_hint=None, fixture_id=None):
    # ★ 优先按 fixture_id 直查（100% 准确）
    if fixture_id:
        fixture = get_fixture_by_id(fixture_id)
        if not fixture:
            return None, f"未找到比赛 ID {fixture_id}"
        hid = fixture["teams"]["home"]["id"]
        hs = fixture["teams"]["home"]["name"]
        aid = fixture["teams"]["away"]["id"]
        as_ = fixture["teams"]["away"]["name"]
    else:
        hid, hs = search_team(home_name)
        aid, as_ = search_team(away_name)
        if not hid or not aid:
            return None, f"球队搜索失败：{home_name} / {away_name}"
        fixture = None
        if date_hint:
            try:
                bd = datetime.strptime(date_hint, "%Y-%m-%d")
                for off in [0, -1, 1, -2, 2, -3, 3, -4, 4]:
                    d = (bd + timedelta(days=off)).strftime("%Y-%m-%d")
                    r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                        params={"date": d, "timezone": "Asia/Shanghai"}, timeout=10)
                    for f in r.json().get("response", []):
                        if f["teams"]["home"]["id"] == hid and f["teams"]["away"]["id"] == aid:
                            fixture = f
                            break
                    if fixture: break
            except Exception:
                pass
        else:
            for off in range(0, 10):
                d = (datetime.now() + timedelta(days=off)).strftime("%Y-%m-%d")
                r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                    params={"date": d, "timezone": "Asia/Shanghai"}, timeout=10)
                for f in r.json().get("response", []):
                    if f["teams"]["home"]["id"] == hid and f["teams"]["away"]["id"] == aid:
                        fixture = f
                        break
                if fixture: break
        if not fixture:
            return None, f"未找到比赛：{hs} vs {as_}"

    fid = fixture["fixture"]["id"]
    lid = fixture["league"]["id"]
    lname = fixture["league"]["name"]
    lcountry = fixture["league"].get("country", "")
    match_date_str = fixture["fixture"]["date"][:10]

    odds = get_odds(fid)
    if not odds[0]:
        return None, f"未找到赔率：{hs} vs {as_}（可能未开盘或数据源未提供）"

    injuries = get_injuries(fid)
    h2h = get_h2h(hid, aid)
    hr_all = get_recent_form(hid, last=10)
    ar_all = get_recent_form(aid, last=10)
    hr = hr_all[:6]
    ar = ar_all[:6]

    lineups = []
    try: lineups = get_lineups_safe(fid)
    except Exception: lineups = []

    referee_name = ""
    try: referee_name = fixture["fixture"].get("referee", "") or ""
    except Exception: referee_name = ""

    standings = []
    try: standings = get_standings_safe(lid)
    except Exception: standings = []

    inj_coef, _, _ = calc_injury_coef(injuries, hid, aid)
    h2h_coef = calc_h2h_coef(h2h, hid)
    form_coef = calc_form_diff(hr, ar, hid, aid)

    rest_days_home, sched_home = calc_schedule_density(hr_all, hid, match_date_str)
    rest_days_away, sched_away = calc_schedule_density(ar_all, aid, match_date_str)
    if rest_days_home is not None and rest_days_away is not None:
        schedule_coef = round(max(-1.0, min(1.0, sched_home - sched_away)), 2)
    else:
        schedule_coef = 0.0

    travel_km = get_travel_km(hs, as_)
    travel_coef = calc_travel_factor(travel_km)
    _, _, league_cn_tmp, _ = get_league_info(lid, lname)
    eu_pressure = 0.0
    if is_eu_match(league_cn_tmp):
        home_league = get_team_league(hs)
        away_league = get_team_league(as_)
        if home_league and away_league:
            eu_pressure = calc_eu_pressure(home_league, away_league)

    coefs = {"injury": inj_coef, "home_away": 0.3, "h2h": h2h_coef,
        "form": form_coef, "motivation": 0.0, "schedule": schedule_coef,
        "travel": travel_coef, "eu_pressure": eu_pressure}
    health, hscore = check_data_health(injuries, h2h, hr, ar, odds)
    hcn = en_to_cn(hs)
    acn = en_to_cn(as_)
    y_threshold = YELLOW_THRESHOLD.get(league_cn_tmp, 5)

    inj_list = []
    for inj in injuries:
        t_id = inj["team"]["id"]
        team_cn = hcn if t_id == hid else (acn if t_id == aid else "未知")
        pid = inj["player"].get("id")
        stats = get_player_stats(pid) if pid else {"position": "", "minutes": 0, "appearences": 0,
            "yellow": 0, "yellowred": 0, "red": 0}
        raw_pos = inj["player"].get("position", "") or stats["position"]
        reason_cn = translate_injury_reason(inj["player"].get("reason", inj.get("type", "")))
        y = stats.get("yellow", 0)
        yr = stats.get("yellowred", 0)
        rr = stats.get("red", 0)
        reason_lower = (inj["player"].get("reason") or inj.get("type") or "").lower()
        if "red" in reason_lower or rr > 0: status = "🔴 红牌停赛"
        elif "yellow" in reason_lower or "suspended" in reason_lower: status = "🟨 累积黄牌停赛"
        elif y >= y_threshold - 1: status = f"⚠️ 临近停赛 ({y}/{y_threshold}黄)"
        else: status = "伤病"
        inj_list.append({"球队": team_cn, "球员": translate_player(inj["player"].get("name", "")),
            "位置": translate_position(raw_pos), "角色": classify_role(stats["minutes"], stats["appearences"]),
            "原因": reason_cn, "状态": status, "赛季黄牌": y, "赛季红牌": rr + yr})

    h2h_list = [{"日期": m["fixture"]["date"][:10], "主队": en_to_cn(m["teams"]["home"]["name"]),
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

    return {"match_id": fid, "match": f"{hcn} vs {acn}",
        "league_api": lname, "league_country": lcountry, "league_id": lid,
        "odds": odds, "coefs": coefs,
        "injuries": inj_list, "h2h": h2h_list,
        "home_recent": fmt_recent(hr, hid), "away_recent": fmt_recent(ar, aid),
        "health": health, "health_score": hscore, "home_cn": hcn, "away_cn": acn,
        "rest_days_home": rest_days_home, "rest_days_away": rest_days_away,
        "schedule_coef": schedule_coef, "travel_km": travel_km,
        "travel_coef": travel_coef, "eu_pressure": eu_pressure,
        "lineups": lineups, "referee": referee_name, "standings": standings}, None


# ================================================================
# ============ 界面 ============
# ================================================================
tab1, tab2, tab3, tab4 = st.tabs(["📊 分析", "⚙️ 调参/模型", "📚 历史记录", "📈 校准/回测"])

with tab1:
    st.subheader("📅 按日期搜索当日比赛")
    col_a, col_b = st.columns([2, 1])
    with col_a:
        search_date = st.date_input("选择日期", value=datetime.now().date())
    with col_b:
        st.write(""); st.write("")
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
                fid = f["fixture"]["id"]
                home_en = f["teams"]["home"]["name"]
                away_en = f["teams"]["away"]["name"]
                hc = en_to_cn(home_en)
                ac = en_to_cn(away_en)
                lc = LEAGUE_MAP[f["league"]["id"]][2]
                ts = f["fixture"]["date"][11:16]
                opt = f"[{lc}] {hc} vs {ac} ({ts})"
                options.append(opt)
                _d = st.session_state.get("date_fixtures_date", datetime.now().strftime("%Y-%m-%d"))
                # ★ 存 fixture_id + 英文队名 + 日期
                o2m[opt] = f"{fid}###{home_en}||{away_en}@{_d}"
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
                with st.expander("查看已加入列表（含格式诊断）"):
                    for i, sm in enumerate(st.session_state["selected_matches"], 1):
                        fmt = "✅ 含ID（精确匹配）" if "###" in sm else ("⚠️ 无ID（建议清空重加）" if "||" in sm else "❌ 旧格式（建议清空重加）")
                        st.write(f"{i}. {sm}  —  {fmt}")

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
        if mi: all_m.extend([x.strip() for x in mi.split(",") if x.strip()])
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
                # ★ 解析 fixture_id
                fid_used = None
                if "###" in m:
                    try:
                        fid_part, m = m.split("###", 1)
                        fid_used = int(fid_part)
                    except Exception:
                        fid_used = None
                if "@" in m: mp, dp = m.rsplit("@", 1)
                else: mp, dp = m, None
                try:
                    if fid_used:
                        # 有 fixture_id → 直接查
                        r, err = analyze_match(None, None, dp, fixture_id=fid_used)
                    else:
                        # 无 id → 走搜索流程
                        h, a = parse_match(mp)
                        if not h or not a:
                            st.warning(f"无法解析：{mp}")
                            continue
                        r, err = analyze_match(h, a, dp)
                    if err: st.warning(err)
                    else: results.append(r)
                except Exception as e:
                    st.warning(f"分析 {m} 时出错：{e}")
                    continue
            prog.empty()
            if not results:
                st.error("分析失败")
            else:
                st.session_state["results"] = results
                st.session_state["cache_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                saved = 0
                for r in results:
                    try:
                        p = calc_all_probs(r["odds"], r["coefs"], r["league_id"],
                            st.session_state["params"], r["league_api"],
                            schedule_coef=r.get("schedule_coef", 0.0),
                            travel_coef=r.get("travel_coef", 0.0),
                            eu_pressure=r.get("eu_pressure", 0.0))
                        ok = save_to_db({"mid": r["match_id"], "mn": r["match"], "lg": p["league_cn"],
                            "at": st.session_state["cache_time"],
                            "ho": r["odds"][0], "do": r["odds"][1], "ao": r["odds"][2],
                            "cj": json.dumps(r["coefs"], ensure_ascii=False, default=str),
                            "pj": json.dumps({k: (v.tolist() if hasattr(v, 'tolist') else v) for k, v in p.items()}, ensure_ascii=False, default=str),
                            "hs": r["health_score"]})
                        if ok: saved += 1
                    except Exception:
                        continue
                st.success(f"分析完成！共 {len(results)} 场，已存库 {saved} 场")

    if "results" in st.session_state:
        if st.session_state.get("cache_time"):
            st.caption(f"⏱️ 数据缓存于 {st.session_state['cache_time']}")
        params = st.session_state["params"]
        st.markdown("---")
        st.subheader("📋 分析结果总览")
        for r in st.session_state["results"]:
            with st.container(border=True):
                try:
                    p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], params, r["league_api"],
                        schedule_coef=r.get("schedule_coef", 0.0),
                        travel_coef=r.get("travel_coef", 0.0),
                        eu_pressure=r.get("eu_pressure", 0.0))
                except Exception:
                    st.warning(f"计算 {r.get('match','?')} 概率时出错")
                    continue
                src = p.get("model_source", "公式")
                st.markdown(f"### {r['match']}")
                st.caption(f"🏆 {p['league_cn']} | 概率来源：{src} → 模型{int(p['model_w']*100)}% / 市场{int(p['market_w']*100)}%")
                c1, c2, c3 = st.columns(3)
                c1.metric("主胜", f"{p['final'][0]}%")
                c2.metric("平局", f"{p['final'][1]}%")
                c3.metric("客胜", f"{p['final'][2]}%")
                with st.expander("🔍 数据依据"):
                    try:
                        if r.get("lineups"):
                            st.markdown("### ⚽ 首发阵容")
                            for team_data in r["lineups"]:
                                try:
                                    team_obj = team_data.get("team", {})
                                    team_name = en_to_cn(team_obj.get("name", ""))
                                    formation = team_data.get("formation", "未知")
                                    coach = (team_data.get("coach") or {}).get("name", "未知")
                                    st.markdown(f"**{team_name}** · 阵型 {formation} · 主教练 {coach}")
                                    starters = team_data.get("startXI", [])
                                    if starters:
                                        rows = []
                                        for s in starters:
                                            pl = s.get("player", {})
                                            rows.append({"号码": pl.get("number", ""),
                                                "位置": translate_position(pl.get("pos", "")),
                                                "球员": translate_player(pl.get("name", ""))})
                                        st.dataframe(pd.DataFrame(rows), hide_index=True)
                                except Exception:
                                    continue
                    except Exception:
                        pass
                    try:
                        if r.get("referee"):
                            st.markdown(f"### 👨‍⚖️ 主裁判：{r['referee']}")
                    except Exception:
                        pass
                    try:
                        if r.get("standings"):
                            st.markdown("### 📊 联赛排名（当前）")
                            rows = []
                            for team in r["standings"]:
                                try:
                                    tname_en = team.get("team", {}).get("name", "")
                                    tname_cn = en_to_cn(tname_en)
                                    if tname_cn in [r.get("home_cn", ""), r.get("away_cn", "")]:
                                        all_stats = team.get("all", {})
                                        goals = all_stats.get("goals", {})
                                        rows.append({"排名": team.get("rank", ""),
                                            "球队": tname_cn, "积分": team.get("points", 0),
                                            "胜/平/负": f"{all_stats.get('win',0)}/{all_stats.get('draw',0)}/{all_stats.get('lose',0)}",
                                            "进球": goals.get("for", 0), "失球": goals.get("against", 0)})
                                except Exception:
                                    continue
                            if rows:
                                st.dataframe(pd.DataFrame(rows), hide_index=True)
                    except Exception:
                        pass
                    st.markdown(f"**数据健康度：{r['health_score']}%**")
                    for ic, nm, dt in r["health"]:
                        st.markdown(f"- {ic} **{nm}**：{dt}")
                    st.markdown("**扩展特征**")
                    ecol1, ecol2, ecol3 = st.columns(3)
                    ecol1.metric("主队休息", f"{r.get('rest_days_home', '未知')} 天")
                    ecol2.metric("客队休息", f"{r.get('rest_days_away', '未知')} 天")
                    tk = r.get('travel_km')
                    ecol3.metric("旅途距离", f"{int(tk)} km" if tk else "未知")
                    st.caption(f"赛程密度系数 {r.get('schedule_coef', 0)} | 旅途疲劳系数 {r.get('travel_coef', 0)} | 欧战压制 {r.get('eu_pressure', 0)}")
                    st.markdown("**伤停明细**")
                    if r["injuries"]:
                        st.dataframe(pd.DataFrame(r["injuries"]), hide_index=True)
                    else:
                        st.caption("无记录")
                    st.markdown("**五层概率**")
                    st.dataframe(pd.DataFrame({"层级": ["LR", "XGB", "模型融合", "市场", "最终"],
                        "主胜": [f"{p['lr'][0]}%", f"{p['xgb'][0]}%", f"{p['model'][0]}%", f"{p['market'][0]}%", f"**{p['final'][0]}%**"],
                        "平": [f"{p['lr'][1]}%", f"{p['xgb'][1]}%", f"{p['model'][1]}%", f"{p['market'][1]}%", f"**{p['final'][1]}%**"],
                        "客胜": [f"{p['lr'][2]}%", f"{p['xgb'][2]}%", f"{p['model'][2]}%", f"{p['market'][2]}%", f"**{p['final'][2]}%**"]}), hide_index=True)
                    st.markdown("**五项系数**")
                    st.json(r["coefs"])
                    st.markdown(f"**近期战绩 - {r['home_cn']}**")
                    if r["home_recent"]: st.dataframe(pd.DataFrame(r["home_recent"]), hide_index=True)
                    st.markdown(f"**近期战绩 - {r['away_cn']}**")
                    if r["away_recent"]: st.dataframe(pd.DataFrame(r["away_recent"]), hide_index=True)
                    st.markdown("**H2H**")
                    if r["h2h"]: st.dataframe(pd.DataFrame(r["h2h"]), hide_index=True)
                    st.markdown(f"**赔率**：主 {r['odds'][0]} / 平 {r['odds'][1]} / 客 {r['odds'][2]}")

        st.markdown("---")
        st.subheader("🎯 今日最稳二串一推荐")
        cands = []
        for r in st.session_state["results"]:
            try:
                p = calc_all_probs(r["odds"], r["coefs"], r["league_id"], params, r["league_api"],
                    schedule_coef=r.get("schedule_coef", 0.0),
                    travel_coef=r.get("travel_coef", 0.0),
                    eu_pressure=r.get("eu_pressure", 0.0))
                pf = p["final"]
                mxi = int(np.argmax(pf))
                if pf[mxi] > 60 and 1.30 <= r["odds"][mxi] <= 2.50 and r["health_score"] >= 80:
                    cands.append({"match": r["match"], "league": p["league_cn"],
                        "pick": ["主胜", "平局", "客胜"][mxi],
                        "prob": float(pf[mxi]), "odd": r["odds"][mxi], "health": r["health_score"]})
            except Exception:
                continue
        best, bs = None, 0
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                c1, c2 = cands[i], cands[j]
                if c1["match"] == c2["match"]: continue
                to = c1["odd"] * c2["odd"]
                if 1.7 <= to <= 4.0:
                    hr = (c1["prob"] / 100) * (c2["prob"] / 100)
                    if hr > bs: bs, best = hr, (c1, c2, to, hr)
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
        st.warning("⚠️ 尚未加载模型。当前分析使用'公式模式'。")
        st.caption("点击【🚀 一键学习】训练真模型。")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🚀 一键学习", type="primary"):
            with st.spinner("正在下载历史数据并训练模型..."):
                try:
                    result, metrics = run_full_training()
                    if result is None:
                        st.error("训练失败：未下载到任何历史数据")
                    else:
                        blob = serialize_model(*result)
                        save_model_to_db(blob, metrics)
                        save_training_log(metrics)
                        st.session_state["model_tuple"] = result
                        st.session_state["model_meta"] = {"trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "samples": metrics["samples"], "lr_logloss": metrics["lr_logloss"],
                            "xgb_logloss": metrics["xgb_logloss"]}
                        st.session_state["model_loaded"] = True
                        st.success(f"✅ 训练完成！样本 {metrics['samples']:,} 场")
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
    st.subheader("⚙️ 参数调优（联赛差异化）")
    scope_options = ["🌐 全局默认"] + SUPPORTED_LEAGUES
    scope = st.selectbox("调参范围", scope_options, index=0)
    if scope == "🌐 全局默认":
        scope_params = st.session_state["params"]["default"]; scope_key = None
    else:
        if scope not in st.session_state["params"]["by_league"]:
            st.session_state["params"]["by_league"][scope] = copy.deepcopy(st.session_state["params"]["default"])
        scope_params = st.session_state["params"]["by_league"][scope]; scope_key = scope
    if scope_key:
        default_w = st.session_state["params"]["default"]["weights"]
        cur_w = scope_params["weights"]
        diffs = [f"{k}: {default_w[k]:.2f} → {cur_w[k]:.2f}" for k in cur_w if abs(cur_w[k] - default_w[k]) > 0.001]
        if diffs: st.info(f"与全局默认的差异： {' | '.join(diffs)}")
        else: st.caption("当前与全局默认一致")
    params_now = copy.deepcopy(scope_params)

    st.markdown("**① 五项系数权重**")
    c1, c2 = st.columns(2)
    with c1:
        params_now["weights"]["injury"] = st.slider(f"{scope} · 伤停", 0.0, 0.5, params_now["weights"]["injury"], 0.01, key=f"inj_{scope}")
        params_now["weights"]["home_away"] = st.slider(f"{scope} · 主客场", 0.0, 0.5, params_now["weights"]["home_away"], 0.01, key=f"ha_{scope}")
        params_now["weights"]["h2h"] = st.slider(f"{scope} · H2H", 0.0, 0.5, params_now["weights"]["h2h"], 0.01, key=f"h2h_{scope}")
    with c2:
        params_now["weights"]["form"] = st.slider(f"{scope} · 近期状态", 0.0, 0.5, params_now["weights"]["form"], 0.01, key=f"form_{scope}")
        params_now["weights"]["motivation"] = st.slider(f"{scope} · 战意", 0.0, 0.5, params_now["weights"]["motivation"], 0.01, key=f"mot_{scope}")
        tw = sum(params_now["weights"].values())
        if abs(tw - 1.0) > 0.01: st.warning(f"⚠️ 合计 {tw:.2f}")
        else: st.success(f"✅ 合计 {tw:.2f}")

    st.markdown("**② 扩展特征权重**")
    if "extended_weights" not in params_now:
        params_now["extended_weights"] = {"schedule": 0.5, "travel": 0.3, "eu_pressure": 0.5}
    params_now["extended_weights"]["schedule"] = st.slider(f"{scope} · 赛程密度", 0.0, 2.0, float(params_now["extended_weights"].get("schedule", 0.5)), 0.05, key=f"sch_{scope}")
    params_now["extended_weights"]["travel"] = st.slider(f"{scope} · 旅途疲劳", 0.0, 2.0, float(params_now["extended_weights"].get("travel", 0.3)), 0.05, key=f"trv_{scope}")
    params_now["extended_weights"]["eu_pressure"] = st.slider(f"{scope} · 欧战压制", 0.0, 2.0, float(params_now["extended_weights"].get("eu_pressure", 0.5)), 0.05, key=f"eu_{scope}")

    st.markdown("**③ 模型融合比例**")
    params_now["model_fusion"]["lr"] = st.slider(f"{scope} · LR", 0.0, 1.0, params_now["model_fusion"]["lr"], 0.01, key=f"lr_{scope}")
    params_now["model_fusion"]["xgb"] = round(1 - params_now["model_fusion"]["lr"], 2)
    st.caption(f"XGB = {params_now['model_fusion']['xgb']}")

    st.markdown("**④ 融合覆盖（可选）**")
    use_ovr = st.checkbox("启用（忽略联赛默认比例）", value=params_now.get("market_fusion_override") is not None, key=f"ovr_{scope}")
    if use_ovr:
        ov = st.slider(f"{scope} · 模型权重", 0.0, 1.0, params_now.get("market_fusion_override") or 0.55, 0.01, key=f"ovv_{scope}")
        params_now["market_fusion_override"] = ov
    else:
        params_now["market_fusion_override"] = None

    if scope_key is None:
        st.session_state["params"]["default"] = params_now
    else:
        st.session_state["params"]["by_league"][scope_key] = params_now

    ca, cb, cc = st.columns(3)
    with ca:
        if st.button("💾 保存为版本"):
            st.session_state["param_versions"].append({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "scope": scope, "params": copy.deepcopy(params_now)})
            st.success(f"已保存（{scope}）")
    with cb:
        if st.button("↩️ 恢复本范围默认"):
            if scope_key is None: st.session_state["params"]["default"] = _base_params()
            else: st.session_state["params"]["by_league"][scope_key] = copy.deepcopy(st.session_state["params"]["default"])
            st.success("已恢复")
            st.rerun()
    with cc:
        if st.button("🔄 全部恢复出厂"):
            st.session_state["params"] = get_default_params()
            st.success("已重置")
            st.rerun()

with tab3:
    st.subheader("📚 历史分析记录")
    if "auto_checked_tab3" not in st.session_state:
        st.session_state["auto_checked_tab3"] = True
        try:
            with st.spinner("正在检查赛果..."):
                _n = auto_update_results()
            if _n > 0: st.success(f"✅ 已自动回填 {_n} 场比赛赛果")
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
                        if pred == h["actual_result"]: hits += 1
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

with tab4:
    st.subheader("📈 概率校准分析")
    st.caption("校准 = 对比模型给出的概率与实际发生频率。")
    cal = calc_calibration()
    if cal is None:
        st.info("样本不足 10 场，暂无法进行校准分析。")
    else:
        st.markdown("**主胜概率区间 vs 实际主胜率**")
        df_cal = pd.DataFrame(cal)
        st.dataframe(df_cal, hide_index=True)
        st.markdown("**判定**")
        for row in cal:
            dev = row["偏差"]
            if abs(dev) < 5:
                st.markdown(f"✅ **{row['概率区间']}**：预测 {row['预测均值']}% → 实际 {row['实际主胜率']}%（准确）")
            elif dev > 5:
                st.markdown(f"⚠️ **{row['概率区间']}**：预测 {row['预测均值']}% → 实际 {row['实际主胜率']}%（低估）")
            else:
                st.markdown(f"⚠️ **{row['概率区间']}**：预测 {row['预测均值']}% → 实际 {row['实际主胜率']}%（高估）")
    st.markdown("---")
    st.subheader("📊 历史 LogLoss")
    ol = calc_overall_logloss()
    if ol:
        loss, n = ol
        c1, c2 = st.columns(2)
        c1.metric("平均 LogLoss", f"{loss}")
        c2.metric("已回填比赛", f"{n} 场")
        st.caption("LogLoss 越低越好。0.90 以下优秀，1.00 左右正常，1.10 以上偏弱。")
    else:
        st.info("暂无足够的已回填比赛")
    st.markdown("---")
    st.subheader("📜 训练日志")
    logs = load_training_logs(30)
    if not logs:
        st.info("暂无训练记录")
    else:
        for log in logs:
            with st.container(border=True):
                st.markdown(f"**{log['trained_at']}**")
                c1, c2, c3 = st.columns(3)
                c1.metric("样本", f"{log['samples']:,}")
                c2.metric("LR LogLoss", f"{log['lr_logloss']:.4f}")
                c3.metric("XGB LogLoss", f"{log['xgb_logloss']:.4f}")
                if log.get("notes"): st.caption(log["notes"])
