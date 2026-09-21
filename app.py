import streamlit as st
import os
import requests
from sqlalchemy import create_engine, text

st.set_page_config(page_title="足球分析模型 - 连通性测试", layout="wide", page_icon="⚽")
st.title("⚽ 第二阶段：数据源与数据库连通性测试")

# 1. 读取密钥
api_key = os.environ.get("API_FOOTBALL_KEY", "")
db_url = os.environ.get("DB_URL", "")

# 2. 测试数据库连接
st.subheader("1. 数据库连接测试")
if not db_url.startswith("postgresql"):
    st.error("❌ DB_URL 未配置或格式错误（必须以 postgresql:// 开头）")
else:
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            st.success("✅ Supabase 数据库连接成功！")
            # 写入一条测试数据
            conn.execute(text("INSERT INTO matches (match_id, league_name, home_team_name, away_team_name) VALUES (999999, '测试联赛', '主队', '客队') ON CONFLICT DO NOTHING"))
            conn.commit()
            st.success("✅ 数据库写入测试成功！")
    except Exception as e:
        st.error(f"❌ 数据库连接失败，报错信息：{e}")

# 3. 测试 API-Football
st.subheader("2. API-Football 连接测试")
if not api_key:
    st.error("❌ API_FOOTBALL_KEY 未配置")
else:
    try:
        url = "https://v3.football.api-sports.io/fixtures"
        params = {"date": "2026-09-21", "league": 39, "season": 2026}
        headers = {"x-apisports-key": api_key}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        data = response.json()
        
        if response.status_code == 200 and "response" in data:
            st.success(f"✅ API-Football 连接成功！今日英超返回 {len(data['response'])} 场比赛数据。")
            if len(data["response"]) > 0:
                st.json(data["response"][0])
        else:
            st.error(f"❌ API 返回异常：{data}")
    except Exception as e:
        st.error(f"❌ API 请求失败，报错信息：{e}")