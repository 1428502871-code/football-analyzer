import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="足球分析模型", layout="wide", page_icon="?")

DB_URL = os.environ.get("DB_URL", "未配置")
db_status = "? 数据库连接串读取成功！" if DB_URL.startswith("postgresql") else "?? 未配置数据库连接串"
st.sidebar.success(db_status)

st.title("? 足球分析模型 - 批量分析总览")

if 'match_list' not in st.session_state:
    st.session_state.match_list = [
        {"id": 1, "match": "阿森纳 vs 切尔西", "model": "48% / 27% / 25%", "market": "45% / 28% / 27%", "final": "47% / 27% / 26%", "tag": "? 市场一致"},
        {"id": 2, "match": "皇马 vs 巴萨", "model": "35% / 28% / 37%", "market": "40% / 25% / 35%", "final": "38% / 26% / 36%", "tag": "? 市场一致"},
        {"id": 3, "match": "曼城 vs 伯恩利", "model": "35% / 15% / 50%", "market": "75% / 15% / 10%", "final": "53% / 15% / 32%", "tag": "?? 模型强逆市场"},
    ]

st.subheader("?? 今日赛事批量分析")
match_input = st.text_input("输入比赛（自由格式，用逗号分隔，例如：阿森纳 切尔西, 皇马 巴萨）")

if st.button("开始分析", type="primary"):
    if match_input:
        st.success(f"已接收 {len(match_input.split(','))} 场比赛，开始批量抓取和分析...")
        st.info("真实模型上线后，这里会显示进度条。")
    else:
        st.warning("请输入至少一场比赛")

for m in st.session_state.match_list:
    with st.container(border=True):
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
        col1.markdown(f"**{m['match']}**")
        col2.caption(f"模型: {m['model']}")
        col3.caption(f"市场: {m['market']}")
        col4.markdown(f"**最终: {m['final']}**")
        col5.markdown(m['tag'])
        
        with st.expander("?? 点击查看数据依据详情"):
            st.markdown("### ?? 本场数据健康度：93%")
            st.markdown("""
            - ? 赔率数据：完整（Pinnacle，赛前1h）
            - ? 伤停数据：完整（API-Football + Flashscore 交叉验证一致）
            - ?? xG数据：缺失（已降级为实际进球估算，置信度降低）
            - ? 计算逻辑：五项系数校验通过，融合概率总和为100%
            """)
            st.markdown("### ?? 伤停明细")
            st.dataframe(pd.DataFrame({
                "球队": ["主队", "主队", "客队"],
                "球员": ["梅里诺", "本·怀特", "福法纳"],
                "位置": ["中场", "后卫", "后卫"],
                "原因": ["伤病", "停赛", "停赛"],
                "权重": [0.8, 0.9, 1.1]
            }), hide_index=True)
            st.caption("数据源：API-Football · 抓取时间：2026-09-21 20:00")
            
            st.markdown("### ?? 近期状态 (含传控/射门比)")
            st.dataframe(pd.DataFrame({
                "球队": ["主队", "客队"],
                "xG-xGA": [+0.8, +0.2],
                "射门(射正)": ["15.2 (5.8)", "9.1 (3.2)"],
                "射门比": [1.79, 0.64],
                "控球率": ["62%", "45%"]
            }), hide_index=True)
            
            st.markdown("### ?? 历史交战 (H2H)")
            st.write("近5次交锋：主队3胜1平1负，加权得分 +0.45")
            
            st.markdown("### ?? 市场赔率变动")
            st.dataframe(pd.DataFrame({
                "时间点": ["开盘", "赛前24h", "赛前1h", "临场"],
                "主胜赔率": [1.50, 1.45, 1.43, 1.42]
            }), hide_index=True)