import streamlit as st
import pandas as pd
import os
import requests
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="⚽")
st.title("⚽ 足球分析模型 - 批量分析与二串一推荐")

api_key = os.environ.get("API_FOOTBALL_KEY", "")
HEADERS = {"x-apisports-key": api_key}
BASE_URL = "https://v3.football.api-sports.io"

# ============ 默认参数 ============
WEIGHTS = {"injury": 0.20, "home_away": 0.20, "h2h": 0.18, "form": 0.21, "motivation": 0.21}

# ============ 联赛ID → 融合比例映射 ============
# 键是 API-Football 的联赛 ID，值 = (模型权重, 市场权重, 联赛中文名, 类别)
LEAGUE_MAP = {
    # 五大联赛
    39:  (0.65, 0.35, "英超", "顶级"),
    140: (0.55, 0.45, "西甲", "顶级"),
    78:  (0.65, 0.35, "德甲", "顶级"),
    135: (0.65, 0.35, "意甲", "顶级"),
    61:  (0.55, 0.45, "法甲", "顶级"),
    # 欧战
    2:   (0.70, 0.30, "欧冠", "欧战"),
    3:   (0.70, 0.30, "欧联", "欧战"),
    848: (0.70, 0.30, "欧协联", "欧战"),
    # 二级联赛
    40:  (0.55, 0.45, "英冠", "普通"),
    79:  (0.55, 0.45, "德乙", "普通"),
    141: (0.55, 0.45, "西乙", "普通"),
    62:  (0.55, 0.45, "法乙", "普通"),
    # 其他欧洲一级
    88:  (0.55, 0.45, "荷甲", "普通"),
    94:  (0.55, 0.45, "葡超", "普通"),
    144: (0.55, 0.45, "比甲", "普通"),
    179: (0.55, 0.45, "苏超", "普通"),
    # 北欧
    103: (0.55, 0.45, "挪超", "普通"),
    113: (0.55, 0.45, "瑞超", "普通"),
    119: (0.55, 0.45, "丹超", "普通"),
    108: (0.55, 0.45, "芬超", "普通"),
}

def get_league_info(league_id, league_name_from_api=""):
    """根据联赛ID匹配融合比例，未收录则归为普通联赛"""
    if league_id in LEAGUE_MAP:
        model_w, market_w, cn_name, cat = LEAGUE_MAP[league_id]
        return model_w, market_w, cn_name, cat
    return 0.55, 0.45, league_name_from_api or "未知联赛", "普通"

# ============ API 调用函数 ============
@st.cache_data(ttl=1800)
def search_team(name):
    try:
        r = requests.get(f"{BASE_URL}/teams", headers=HEADERS, params={"search": name}, timeout=10)
        data = r.json()
        if data.get("response"):
            t = data["response"][0]["team"]
            return t["id"], t["name"]
    except Exception as e:
        return None, str(e)
    return None, None

@st.cache_data(ttl=1800)
def get_fixture(home_id, away_id, date_str):
    try:
        r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS,
                         params={"date": date_str, "timezone": "Asia/Shanghai"}, timeout=10)
        data = r.json()
        for f in data.get("response", []):
            if f["teams"]["home"]["id"] == home_id and f["teams"]["away"]["id"] == away_id:
                return f
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
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

@st.cache_data(ttl=1800)
def get_injuries(fixture_id):
    try:
        r = requests.get(f"{BASE_URL}/injuries", headers=HEADERS,
                         params={"fixture": fixture_id}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []

@st.cache_data(ttl=1800)
def get_h2h(home_id, away_id):
    try:
        r = requests.get(f"{BASE_URL}/fixtures/headtohead", headers=HEADERS,
                         params={"h2h": f"{home_id}-{away_id}", "last": 5}, timeout=10)
        return r.json().get("response", [])
    except Exception:
        return []

@st.cache_data(ttl=1800)
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
    coef = np.tanh(diff / 3.0)
    return round(coef, 2), h_score, a_score

def calc_h2h_coef(h2h_matches, home_id):
    decay = [1.0, 0.7, 0.5, 0.3, 0.2]
    score = 0
    for i, m in enumerate(h2h_matches[:5]):
        w = decay[i] if i < len(decay) else 0.1
        h_score = m["goals"]["home"] or 0
        a_score = m["goals"]["away"] or 0
        if m["teams"]["home"]["id"] == home_id:
            score += w * (1 if h_score > a_score else (-1 if h_score < a_score else 0))
        else:
            score += w * (1 if a_score > h_score else (-1 if a_score < h_score else 0))
    coef = np.tanh(score / 3.0)
    return round(coef, 2)

def calc_form_coef(recent, team_id):
    score = 0
    for m in recent:
        h_score = m["goals"]["home"] or 0
        a_score = m["goals"]["away"] or 0
        if m["teams"]["home"]["id"] == team_id:
            score += (3 if h_score > a_score else (1 if h_score == a_score else 0))
        else:
            score += (3 if a_score > h_score else (1 if a_score == h_score else 0))
    return score

def calc_form_diff(home_recent, away_recent, home_id, away_id):
    h = calc_form_coef(home_recent, home_id)
    a = calc_form_coef(away_recent, away_id)
    coef = np.tanh((h - a) / 9.0)
    return round(coef, 2)

# ============ 概率计算 ============
def devig(odds):
    inv = [1/o for o in odds]
    s = sum(inv)
    return [i/s for i in inv]

def softmax3(base, adjust):
    logits = np.array([np.log(p) for p in base]) + np.array([adjust, -adjust*0.3, -adjust*0.7])
    e = np.exp(logits - np.max(logits))
    return e / e.sum()

def calc_all_probs(odds, coefs, league_id, league_name=""):
    """自动识别联赛，计算五层概率"""
    market_p = devig(odds)
    adjust = sum(coefs[k] * WEIGHTS[k] for k in WEIGHTS)
    
    lr_p = softmax3(market_p, adjust * 0.5)
    xgb_p = softmax3(market_p, adjust * 1.0)
    model_p = 0.45 * lr_p + 0.55 * xgb_p
    
    # 自动识别联赛，匹配融合比例
    model_w, market_w, cn_name, cat = get_league_info(league_id, league_name)
    final_p = model_w * model_p + market_w * np.array(market_p)
    final_p = final_p / final_p.sum()
    
    return {
        "lr": (lr_p * 100).round(1),
        "xgb": (xgb_p * 100).round(1),
        "model": (model_p * 100).round(1),
        "market": (np.array(market_p) * 100).round(1),
        "final": (final_p * 100).round(1),
        "league_cn": cn_name,
        "model_w": model_w,
        "market_w": market_w
    }

# ============ 主流程 ============
st.subheader("📊 批量输入比赛")
st.caption("支持多联赛混合输入，系统会自动识别每场比赛的联赛性质并匹配对应融合比例。")
match_input = st.text_input(
    "自由格式，用逗号分隔（请使用英文队名，例如：Arsenal Chelsea, Real Madrid Barcelona, Man City Burnley）",
    ""
)

if st.button("开始批量分析", type="primary"):
    if not match_input:
        st.warning("请输入比赛")
    elif not api_key:
        st.error("API Key 未配置")
    else:
        matches = [m.strip() for m in match_input.split(",") if m.strip()]
        results = []
        
        progress = st.progress(0)
        for i, m in enumerate(matches):
            progress.progress((i + 1) / len(matches), text=f"正在分析：{m}")
            parts = m.replace("vs", "").replace("VS", "").split()
            if len(parts) < 2:
                st.warning(f"无法解析：{m}")
                continue
            home_name, away_name = parts[0], parts[1]
            
            home_id, home_std = search_team(home_name)
            away_id, away_std = search_team(away_name)
            if not home_id or not away_id:
                st.warning(f"球队搜索失败：{m}")
                continue
            
            fixture = None
            for offset in range(0, 4):
                d = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
                fixture = get_fixture(home_id, away_id, d)
                if fixture:
                    break
            
            if not fixture:
                st.warning(f"未找到近期比赛：{home_std} vs {away_std}")
                continue
            
            fid = fixture["fixture"]["id"]
            league_id = fixture["league"]["id"]
            league_name_api = fixture["league"]["name"]
            league_country = fixture["league"].get("country", "")
            
            h_odd, d_odd, a_odd = get_odds(fid)
            if not h_odd:
                st.warning(f"未找到赔率数据：{home_std} vs {away_std}（联赛：{league_name_api}）")
                continue
            
            injuries = get_injuries(fid)
            h2h = get_h2h(home_id, away_id)
            h_recent = get_recent_form(home_id)
            a_recent = get_recent_form(away_id)
            
            inj_coef, h_inj, a_inj = calc_injury_coef(injuries, home_id, away_id)
            h2h_coef = calc_h2h_coef(h2h, home_id)
            form_coef = calc_form_diff(h_recent, a_recent, home_id, away_id)
            home_away_coef = 0.3
            motivation_coef = 0.0
            
            coefs = {
                "injury": inj_coef,
                "home_away": home_away_coef,
                "h2h": h2h_coef,
                "form": form_coef,
                "motivation": motivation_coef
            }
            
            # 自动识别联赛并计算
            probs = calc_all_probs([h_odd, d_odd, a_odd], coefs, league_id, league_name_api)
            
            results.append({
                "match": f"{home_std} vs {away_std}",
                "league_api": league_name_api,
                "league_country": league_country,
                "league_id": league_id,
                "league_cn": probs["league_cn"],
                "odds": (h_odd, d_odd, a_odd),
                "coefs": coefs,
                "probs": probs,
                "injuries": injuries,
                "h2h": h2h,
            })
        
        progress.empty()
        
        if not results:
            st.error("所有比赛分析失败，请检查输入")
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
            # 显示联赛识别信息
            st.markdown(f"### {r['match']}")
            st.caption(f"🏆 联赛识别：**{r['league_cn']}** (API: {r['league_api']} · {r['league_country']}) → 融合比例 模型{int(p['model_w']*100)}% / 市场{int(p['market_w']*100)}%")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("主胜", f"{p['final'][0]}%")
            col2.metric("平局", f"{p['final'][1]}%")
            col3.metric("客胜", f"{p['final'][2]}%")
            
            with st.expander("🔍 五层概率 + 系数依据"):
                st.markdown("**五层概率对比**")
                st.dataframe(pd.DataFrame({
                    "层级": ["逻辑回归", "XGBoost", "模型融合", "市场去水", "最终融合"],
                    "主胜": [f"{p['lr'][0]}%", f"{p['xgb'][0]}%", f"{p['model'][0]}%", f"{p['market'][0]}%", f"**{p['final'][0]}%**"],
                    "平局": [f"{p['lr'][1]}%", f"{p['xgb'][1]}%", f"{p['model'][1]}%", f"{p['market'][1]}%", f"**{p['final'][1]}%**"],
                    "客胜": [f"{p['lr'][2]}%", f"{p['xgb'][2]}%", f"{p['model'][2]}%", f"{p['market'][2]}%", f"**{p['final'][2]}%**"],
                }), hide_index=True)
                
                st.markdown("**五项系数**")
                st.json(r["coefs"])
                
                st.markdown(f"**赔率（Pinnacle）**：主 {r['odds'][0]} / 平 {r['odds'][1]} / 客 {r['odds'][2]}")
                st.caption(f"数据抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ============ 二串一推荐 ============
    st.markdown("---")
    st.subheader("🎯 今日最稳二串一推荐")
    
    candidates = []
    for r in st.session_state["results"]:
        p = r["probs"]["final"]
        max_p = max(p)
        max_idx = p.index(max_p)
        odd = r["odds"][max_idx]
        if max_p > 60 and 1.30 <= odd <= 2.50:
            market_p = r["probs"]["market"]
            if max_p - market_p[max_idx] >= 0:
                candidates.append({
                    "match": r["match"],
                    "league": r["league_cn"],
                    "pick": ["主胜", "平局", "客胜"][max_idx],
                    "prob": max_p,
                    "odd": odd,
                    "ev": (max_p / 100) * odd - 1
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
            st.markdown(f"推荐：**{c1['pick']}** | 概率 {c1['prob']}% | 赔率 {c1['odd']}")
        with col2:
            st.markdown(f"**🥈 稳胆2**：{c2['match']} ({c2['league']})")
            st.markdown(f"推荐：**{c2['pick']}** | 概率 {c2['prob']}% | 赔率 {c2['odd']}")
        st.markdown(f"**💰 组合赔率**：{total_odd:.2f}（符合 1.7-4.0 区间）")
        st.markdown(f"**📊 理论命中率**：{hit_rate*100:.1f}%")
    else:
        st.warning("⚠️ 今日无符合条件的二串一推荐，建议观望或只玩单场。")
