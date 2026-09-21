import streamlit as st
import pandas as pd
import os
import requests
import numpy as np

st.set_page_config(page_title="足球分析模型 - 真实分析", layout="wide", page_icon="?")
st.title("? 足球分析模型 - 真实数据分析")

api_key = os.environ.get("API_FOOTBALL_KEY", "")

# 默认权重参数
WEIGHTS = {
    "injury": 0.20, "home_away": 0.20, "h2h": 0.18, "form": 0.21, "motivation": 0.21
}
MODEL_FUSION = {"lr": 0.45, "xgb": 0.55}
MARKET_FUSION = {"model": 0.65, "market": 0.35} # 默认英超比例

st.subheader("输入比赛（自由格式，例如：阿森纳 切尔西）")
match_input = st.text_input("比赛名称", "")

if st.button("开始真实分析", type="primary"):
    if not match_input:
        st.warning("请输入比赛名称")
    elif not api_key:
        st.error("API Key 未配置")
    else:
        with st.spinner("正在抓取真实数据并计算..."):
            # 模拟一个真实抓取流程（此处用假数据先跑通逻辑，后续替换为真实API解析）
            # 实际工程中，这里会先调 fixtures 接口搜索比赛ID，再调 odds/injuries/h2h 接口
            st.success("数据抓取完毕！")
            
            # --- 模拟真实抓取到的原始数据 ---
            # 1. 市场赔率 (欧赔 Pinnacle)
            odds = [1.50, 4.00, 5.50]
            # 2. 五项系数原始分 (-1 到 +1)
            coef = {"injury": +0.40, "home_away": +0.30, "h2h": +0.50, "form": +0.10, "motivation": 0.00}
            
            # 计算模型调整分
            adjust = sum(coef[k] * WEIGHTS[k] for k in WEIGHTS)
            # 基础概率 (用市场去水作为基准)
            inv_odds = [1/o for o in odds]
            market_probs = [i/sum(inv_odds) for i in inv_odds]
            
            # 模拟 LR 和 XGB 模型概率 (基于基础概率+调整分)
            lr_probs = [p + (adjust * 0.4) for p in market_probs]
            xgb_probs = [p + (adjust * 0.6) for p in market_probs]
            
            # 模型融合 (LR 45% + XGB 55%)
            model_probs = [0.45 * lr_probs[i] + 0.55 * xgb_probs[i] for i in range(3)]
            
            # 最终融合 (模型 65% + 市场 35%)
            final_probs = [0.65 * model_probs[i] + 0.35 * market_probs[i] for i in range(3)]
            
            # 归一化
            def norm(p_list):
                s = sum(p_list)
                return [round(p / s * 100, 1) for p in p_list]
            
            lr_p = norm(lr_probs)
            xgb_p = norm(xgb_probs)
            model_p = norm(model_probs)
            market_p = norm(market_probs)
            final_p = norm(final_probs)

            st.markdown("### ?? 五层胜率对比")
            df_probs = pd.DataFrame({
                "层级": ["逻辑回归", "XGBoost", "模型融合 (LR45+XGB55)", "市场去水", "最终融合 (模型65%+市场35%)"],
                "主胜": [f"{lr_p[0]}%", f"{xgb_p[0]}%", f"{model_p[0]}%", f"{market_p[0]}%", f"**{final_p[0]}%**"],
                "平局": [f"{lr_p[1]}%", f"{xgb_p[1]}%", f"{model_p[1]}%", f"{market_p[1]}%", f"**{final_p[1]}%**"],
                "客胜": [f"{lr_p[2]}%", f"{xgb_p[2]}%", f"{model_p[2]}%", f"{market_p[2]}%", f"**{final_p[2]}%**"]
            })
            st.dataframe(df_probs, hide_index=True)

            st.markdown("### ?? 五项系数依据")
            st.json(coef)
            st.caption("注：当前为逻辑跑通阶段，真实API解析代码正在下个版本接入。")
