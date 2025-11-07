"""
Streamlit アプリケーション - 馬詳細ページ
特定の馬の成績指標と過去レース結果を詳細表示
"""

import streamlit as st
from pathlib import Path
import sys

# プロジェクトルートをsys.pathに追加
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.lib import queries, charts

st.set_page_config(
    page_title="馬詳細 - 競馬データベース",
    page_icon="🐴",
    layout="wide",
)

# ========================
# ページ初期化
# ========================

if "selected_horse_id" not in st.session_state:
    st.error("❌ 馬が選択されていません")
    st.stop()

horse_id = st.session_state.selected_horse_id

# 馬情報を取得
horse_details = queries.get_horse_details(horse_id)

if not horse_details:
    st.error(f"❌ 馬ID {horse_id} の情報が見つかりません")
    st.stop()

# ========================
# ページヘッダー
# ========================

horse_name = horse_details.get("raw_name", "不明")

st.title(f"🐴 {horse_name}")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown(f"**ID**: {horse_id}")
    if horse_details.get("sex"):
        st.markdown(f"**性別**: {horse_details['sex']}")
    if horse_details.get("birth_year"):
        st.markdown(f"**生年**: {horse_details['birth_year']}")

with col2:
    if st.button("← 戻る"):
        st.switch_page("Home.py")

st.markdown("---")

# ========================
# 主要指標
# ========================

st.subheader("📈 主要指標")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("出走数", int(horse_details.get("races_count", 0)))

with col2:
    win_rate = horse_details.get("win_rate", 0) * 100
    st.metric("勝率", f"{win_rate:.2f}%")

with col3:
    place_rate = horse_details.get("place_rate", 0) * 100
    st.metric("連対率", f"{place_rate:.2f}%")

with col4:
    show_rate = horse_details.get("show_rate", 0) * 100
    st.metric("複勝率", f"{show_rate:.2f}%")

with col5:
    recent_score = horse_details.get("recent_score", 0)
    st.metric("近走指数", f"{recent_score:.2f}")

st.markdown("---")

# ========================
# 過去成績詳細
# ========================

st.subheader("📊 過去成績")

history = queries.get_horse_race_history(horse_id, limit=100)

if history:
    # テーブル表示
    history_df = charts.create_horse_history_table(history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # グラフ表示
    st.subheader("📉 分析グラフ")

    tab1, tab2, tab3 = st.tabs(["近走指数", "距離別成績", "馬場別成績"])

    with tab1:
        fig = charts.create_recent_score_chart(history)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "💡 近走指数は最近のレース成績を基に計算されます。"
            "古いレースほど重みが低くなります。"
        )

    with tab2:
        fig = charts.create_distance_preference_chart(
            horse_details.get("distance_pref", "{}")
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "💡 距離別成績は、その距離でのレース成績をまとめたものです。"
            "得意距離を見つけるのに役立ちます。"
        )

    with tab3:
        fig = charts.create_surface_preference_chart(
            horse_details.get("surface_pref", "{}")
        )
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            "💡 馬場別成績は、馬場状態（芝/ダート）ごとの成績です。"
            "馬場適性を判断する参考になります。"
        )

    # ========================
    # 統計情報
    # ========================

    st.markdown("---")

    st.subheader("📈 統計情報")

    col1, col2, col3 = st.columns(3)

    with col1:
        wins = sum(1 for h in history if h.get("finish_pos") == 1)
        st.metric("勝利数", wins)

    with col2:
        places = sum(1 for h in history if h.get("finish_pos") in (1, 2))
        st.metric("連対数", places)

    with col3:
        shows = sum(1 for h in history if h.get("finish_pos") in (1, 2, 3))
        st.metric("複勝数", shows)

    # ========================
    # 最終更新情報
    # ========================

    st.markdown("---")

    if horse_details.get("updated_at"):
        st.caption(f"最終更新: {horse_details['updated_at']}")

else:
    st.info("ℹ️ このレース馬の過去成績がまだ登録されていません")

# ========================
# 操作
# ========================

st.markdown("---")

if st.button("🔄 キャッシュをクリア"):
    st.cache_data.clear()
    st.rerun()
