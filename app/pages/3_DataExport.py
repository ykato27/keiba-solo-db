"""
Streamlit アプリケーション - データエクスポートページ
JRAデータと学習用特徴量をCSV形式でダウンロード
"""

import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import queries, csv_export

st.set_page_config(
    page_title="データエクスポート - 競馬データベース",
    page_icon="📊",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("📊 データエクスポート")

st.markdown("JRAデータと学習用特徴量をCSV形式でダウンロード")

# ナビゲーションメニュー
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    if st.button("🏠 ホーム", use_container_width=True):
        st.switch_page("Home.py")

with col2:
    if st.button("📅 将来レース", use_container_width=True):
        st.switch_page("pages/2_FutureRaces.py")

with col3:
    if st.button("📊 エクスポート", use_container_width=True, disabled=True):
        pass

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
    if st.button("🏇 レース", use_container_width=True):
        st.switch_page("pages/8_Race.py")

st.markdown("---")

# ========================
# サイドバー
# ========================

from app.sidebar_utils import render_sidebar

render_sidebar()

# ========================
# エクスポートオプション
# ========================

st.subheader("📥 ダウンロードするデータを選択")

export_type = st.radio(
    "エクスポートタイプ",
    options=[
        "1. レース情報",
        "2. 出走馬情報（詳細）",
        "3. 馬のメトリクス",
        "4. 学習用特徴量データ",
    ],
    help="ダウンロードするデータの種類を選択してください",
)

st.markdown("---")

# ========================
# 1. レース情報
# ========================

if "1. レース情報" in export_type:
    st.subheader("🏇 レース情報エクスポート")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input("開始日", value=datetime.now() - timedelta(days=30))

    with col2:
        end_date = st.date_input("終了日", value=datetime.now())

    if st.button("レース情報をCSVでダウンロード", type="primary", use_container_width=True):
        with st.spinner("レース情報を取得中..."):
            csv_data = csv_export.export_all_races_to_csv(
                start_date=str(start_date), end_date=str(end_date)
            )

            if csv_data:
                st.download_button(
                    label="📥 races_data.csv をダウンロード",
                    data=csv_data,
                    file_name=f"races_{start_date}_{end_date}.csv",
                    mime="text/csv",
                )
                st.success(f"✓ レース情報を取得しました")
                st.info(f"期間: {start_date} ～ {end_date}")
            else:
                st.warning("データが見つかりません")

# ========================
# 2. 出走馬情報（詳細）
# ========================

elif "2. 出走馬情報（詳細）" in export_type:
    st.subheader("🐴 出走馬情報エクスポート")

    export_scope = st.radio(
        "エクスポート範囲", options=["全データ", "期間指定", "レース指定"], horizontal=True
    )

    if export_scope == "期間指定":
        col1, col2 = st.columns(2)

        with col1:
            start_date = st.date_input(
                "開始日", value=datetime.now() - timedelta(days=30), key="entry_start"
            )

        with col2:
            end_date = st.date_input("終了日", value=datetime.now(), key="entry_end")

        if st.button("出走馬情報をCSVでダウンロード", type="primary", use_container_width=True):
            with st.spinner("出走馬情報を取得中..."):
                csv_data = csv_export.export_entry_details_to_csv(
                    start_date=str(start_date), end_date=str(end_date)
                )

                if csv_data:
                    st.download_button(
                        label="📥 entry_data.csv をダウンロード",
                        data=csv_data,
                        file_name=f"entries_{start_date}_{end_date}.csv",
                        mime="text/csv",
                    )
                    st.success(f"✓ 出走馬情報を取得しました")
                else:
                    st.warning("データが見つかりません")

    elif export_scope == "レース指定":
        # レース選択
        all_dates = queries.get_all_race_dates()

        if all_dates:
            selected_date = st.selectbox(
                "開催日を選択",
                options=all_dates,
                format_func=lambda x: f"{x} ({len(queries.get_courses_by_date(x))}開催)",
            )

            courses = queries.get_courses_by_date(selected_date)

            if courses:
                selected_course = st.selectbox(
                    "開催場を選択",
                    options=courses,
                )

                races = queries.get_races(selected_date, selected_course)

                if races:
                    race_options = {
                        race[
                            "race_id"
                        ]: f"R{race['race_no']} - {race.get('title', '無題')} ({race['distance_m']}m / {race['surface']})"
                        for race in races
                    }

                    selected_race_id = st.selectbox(
                        "レースを選択",
                        options=list(race_options.keys()),
                        format_func=lambda x: race_options[x],
                    )

                    if st.button(
                        "出走馬情報をCSVでダウンロード", type="primary", use_container_width=True
                    ):
                        with st.spinner("出走馬情報を取得中..."):
                            csv_data = csv_export.export_entry_details_to_csv(
                                race_id=selected_race_id
                            )

                            if csv_data:
                                st.download_button(
                                    label="📥 entry_data.csv をダウンロード",
                                    data=csv_data,
                                    file_name=f"entries_race_{selected_race_id}.csv",
                                    mime="text/csv",
                                )
                                st.success(f"✓ 出走馬情報を取得しました")
                            else:
                                st.warning("データが見つかりません")

    else:  # 全データ
        st.warning(
            "⚠️ 全データエクスポートは大量データを処理するため時間がかかります（最大10,000件）"
        )
        if st.button("全出走馬情報をCSVでダウンロード", type="primary", use_container_width=True):
            with st.spinner("出走馬情報を取得中... (この処理には時間がかかります)"):
                try:
                    csv_data = csv_export.export_entry_details_to_csv()

                    if csv_data:
                        st.download_button(
                            label="📥 all_entries.csv をダウンロード",
                            data=csv_data,
                            file_name=f"all_entries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                        )
                        st.success(f"✓ 出走馬情報を取得しました")
                    else:
                        st.warning("データが見つかりません")
                except Exception as e:
                    st.error(f"エクスポートエラー: {e}")

# ========================
# 3. 馬のメトリクス
# ========================

elif "3. 馬のメトリクス" in export_type:
    st.subheader("📈 馬のメトリクスエクスポート")

    st.info("全馬のメトリクス（勝率、連対率、複勝率など）をCSV形式でエクスポートします")

    if st.button("馬のメトリクスをCSVでダウンロード", type="primary", use_container_width=True):
        with st.spinner("馬のメトリクスを取得中..."):
            csv_data = csv_export.export_horse_metrics_to_csv()

            if csv_data:
                st.download_button(
                    label="📥 horse_metrics.csv をダウンロード",
                    data=csv_data,
                    file_name=f"horse_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
                st.success(f"✓ 馬のメトリクスを取得しました")
            else:
                st.warning("データが見つかりません")

# ========================
# 4. 学習用特徴量データ
# ========================

elif "4. 学習用特徴量データ" in export_type:
    st.subheader("🤖 学習用特徴量データエクスポート")

    st.info(
        """
    **注意**: このエクスポートには以下の情報が含まれます：
    - 着順が記録されているエントリのみ（教師あり学習用）
    - 60+個の複合特徴量（WHO, WHEN, RACE, ENTRY, PEDIGREE）
    - ターゲット変数（1着=0, 2-3着=1, その他=2）
    - 特徴量の計算には時間がかかります
    """
    )

    if st.button("学習用特徴量をCSVでダウンロード", type="primary", use_container_width=True):
        with st.spinner("特徴量を計算中... (この処理には時間がかかります)"):
            try:
                csv_data = csv_export.export_training_features_to_csv()

                if csv_data:
                    st.download_button(
                        label="📥 training_features.csv をダウンロード",
                        data=csv_data,
                        file_name=f"training_features_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )
                    st.success(f"✓ 特徴量データを取得しました")
                    st.info(
                        "このデータはXGBoost、LightGBM、Random Forestなどの機械学習モデルの学習に使用できます"
                    )
                else:
                    st.warning("データが見つかりません")

            except Exception as e:
                st.error(f"特徴量計算エラー: {e}")

st.markdown("---")

# ============================================
# 情報
# ============================================

st.info(
    """
    💡 **CSVデータについて**

    ### レース情報
    - 開催日、開催場、レース番号、距離、馬場など基本情報
    - 期間指定でダウンロード可能

    ### 出走馬情報（詳細）
    - 馬名、騎手、調教師、枠番、斤量など詳細な出走情報
    - 着順、タイムなども含む
    - 全データ、期間指定、単一レース指定から選択可能

    ### 馬のメトリクス
    - 各馬の勝率、連対率、複勝率、最近成績
    - 距離別・馬場別成績
    - 近走指数（最近の成績をスコア化）

    ### 学習用特徴量データ
    - 機械学習の学習に直接使用できる形式
    - 60+個の複合特徴量を含む
    - ターゲット変数（予測対象）を含む
    - 着順が記録されているエントリのみ

    ### エクスポート形式
    - すべてのCSVはUTF-8エンコーディング（BOM付き）
    - Excelで直接開くことが可能
    - 日本語対応
    """
)

st.markdown("---")

st.caption("🔄 最終更新: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
