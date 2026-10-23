"""
Streamlit アプリケーション - レース詳細ページ
レースの出走馬一覧と詳細情報を表示
"""

import streamlit as st
import sys
from pathlib import Path

# 親ディレクトリを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # プロジェクトルート（app/legacy の解決用）

import db
import queries
import charts

st.set_page_config(
    page_title="レース詳細 - 競馬データベース",
    page_icon="🐴",
    layout="wide",
)

# ========================
# ページ初期化
# ========================

if "selected_race_id" not in st.session_state:
    st.error("❌ レースが選択されていません")
    st.stop()

race_id = st.session_state.selected_race_id

# レース情報を取得（これは race_entries から逆引き）
entries = queries.get_race_entries_with_metrics(race_id)

if not entries:
    st.error(f"❌ レースID {race_id} の情報が見つかりません")
    st.stop()

# レース基本情報の取得（最初のエントリーから日付等を取得）
first_entry = entries[0]
race_info = {
    "race_id": race_id,
    # 注：race テーブルから直接取得するのが理想だが、ここでは簡略化
}

# ========================
# ページヘッダー
# ========================

st.title(f"🐴 レース詳細 (ID: {race_id})")

# ナビゲーションメニュー
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    if st.button("🏠 ホーム", use_container_width=True):
        st.switch_page("Home.py")

with col2:
    if st.button("📅 将来レース", use_container_width=True):
        st.switch_page("pages/2_FutureRaces.py")

with col3:
    if st.button("📊 エクスポート", use_container_width=True):
        st.switch_page("pages/3_DataExport.py")

with col4:
    if st.button("🚀 学習", use_container_width=True):
        st.switch_page("pages/4_ModelTraining.py")

with col5:
    if st.button("🔮 予測", use_container_width=True):
        st.switch_page("pages/6_Prediction_Enhanced.py")

with col6:
    if st.button("💰 推奨", use_container_width=True):
        st.switch_page("pages/6_Prediction_Enhanced.py")

with col7:
    if st.button("🐴 馬", use_container_width=True):
        st.switch_page("pages/7_Horse.py")

with col8:
    if st.button("🏇 レース", use_container_width=True, disabled=True):
        pass

st.markdown("---")

# ========================
# サイドバー
# ========================

from app.sidebar_utils import render_sidebar

render_sidebar()

st.markdown(f"**出走馬数**: {len(entries)}")

st.markdown("---")

# ========================
# 出走馬一覧テーブル
# ========================

st.subheader("📋 出走馬一覧")

# テーブル表示用にデータを整形
df = charts.create_race_entries_table(entries)

# テーブル表示
st.dataframe(df, use_container_width=True, hide_index=True)

st.markdown("---")

# ========================
# 馬詳細表示
# ========================

st.subheader("🔍 馬詳細")

# 馬を選択
horse_options = [e["horse_name"] for e in entries if e["horse_name"]]

if not horse_options:
    st.warning("出走馬の詳細情報がありません")
else:
    selected_horse_name = st.selectbox(
        "馬を選択して詳細を表示",
        options=horse_options,
    )

    if selected_horse_name:
        # 選択された馬の情報を取得
        selected_entry = next((e for e in entries if e["horse_name"] == selected_horse_name), None)

        if selected_entry and selected_entry["horse_id"]:
            horse_id = selected_entry["horse_id"]

            # 馬の詳細情報を取得
            horse_details = queries.get_horse_details(horse_id)

            if horse_details:
                # メトリクス表示
                col1, col2, col3, col4, col5 = st.columns(5)

                metrics = charts.create_horse_metrics_display(horse_details)

                with col1:
                    st.metric("出走数", metrics["出走数"])

                with col2:
                    st.metric("勝率", metrics["勝率"])

                with col3:
                    st.metric("連対率", metrics["連対率"])

                with col4:
                    st.metric("複勝率", metrics["複勝率"])

                with col5:
                    st.metric("近走指数", metrics["近走指数"])

                st.markdown("---")

                # 過去成績
                st.subheader("📊 過去成績")

                history = queries.get_horse_race_history(horse_id, limit=20)

                if history:
                    history_df = charts.create_horse_history_table(history)
                    st.dataframe(history_df, use_container_width=True, hide_index=True)

                    st.markdown("---")

                    # グラフ表示
                    col1, col2 = st.columns(2)

                    with col1:
                        fig = charts.create_recent_score_chart(history)
                        st.plotly_chart(fig, use_container_width=True)

                    with col2:
                        fig = charts.create_distance_preference_chart(
                            horse_details.get("distance_pref", "{}")
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    # 馬場別成績
                    fig = charts.create_surface_preference_chart(
                        horse_details.get("surface_pref", "{}")
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 馬詳細へのリンク
                    st.markdown("---")
                    if st.button(
                        f"🔗 {selected_horse_name} の詳細ページへ", key=f"horse_detail_{horse_id}"
                    ):
                        st.session_state.selected_horse_id = horse_id
                        st.switch_page("pages/Horse.py")

                else:
                    st.info("過去成績がまだ登録されていません")

            else:
                st.error("馬情報の取得に失敗しました")
        else:
            st.warning("馬IDが見つかりません")

st.markdown("---")

if st.button("🔄 キャッシュをクリア"):
    st.cache_data.clear()
    st.rerun()
