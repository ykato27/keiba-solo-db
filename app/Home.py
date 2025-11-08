"""
Streamlit アプリケーション - ホームページ
開催日と開催場を選択してレース一覧を表示
"""

import streamlit as st
import sys
import time
from pathlib import Path

# パス設定（早い段階で設定）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app import db
from app import queries
from app import charts
from app import test_data
from app import progress_utils

# ページ設定
st.set_page_config(
    page_title="競馬データベース",
    page_icon="🐴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS スタイル
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .race-card {
        background-color: #ffffff;
        padding: 15px;
        border-left: 5px solid #0066cc;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ========================
# 初期化
# ========================

db.init_schema()

if not db.verify_schema():
    st.error("❌ データベーススキーマが正常ではありません")
    st.stop()

# ========================
# サイドバー
# ========================

from app.sidebar_utils import render_sidebar
render_sidebar()

# ⚙️ 管理者パネル
st.sidebar.subheader("⚙️ 管理者パネル")

st.sidebar.write("**本番データを投入**")
years = st.sidebar.slider("対象年数", 1, 5, 3, help="投入する過去年数（多いほど時間がかかります）")

if st.sidebar.button("📥 本番データを投入", use_container_width=True):
    with st.sidebar.status("処理中...", expanded=True) as status:
        st.write(f"📊 {years}年分のデータを生成中...")
        races = test_data.generate_test_races(years=years)
        horses = test_data.generate_test_horses(count=150 + years*30)
        jockeys = test_data.generate_test_jockeys(count=40 + years*10)
        trainers = test_data.generate_test_trainers(count=40 + years*10)
        entries = test_data.generate_test_entries(races, horses, jockeys, trainers)

        st.write(f"✅ レース: {len(races):,}件")
        st.write(f"✅ 馬: {len(horses):,}件")
        st.write(f"✅ 騎手: {len(jockeys):,}件")
        st.write(f"✅ 調教師: {len(trainers):,}件")
        st.write(f"✅ 出走: {len(entries):,}件")

        # ETL処理
        try:
            from etl import upsert_master, upsert_race, upsert_entry, apply_alias
            from metrics import build_horse_metrics

            start_time = time.time()

            # マスタデータを登録
            st.write("🔄 マスタデータを登録...")
            step_start = time.time()
            upsert_master.MasterDataUpsert().upsert_horses(horses)
            upsert_master.MasterDataUpsert().upsert_jockeys(jockeys)
            upsert_master.MasterDataUpsert().upsert_trainers(trainers)
            step_time = time.time() - step_start
            st.caption(f"✅ 完了: {progress_utils.format_duration(step_time)}")

            # レース情報を登録
            st.write("🔄 レース情報を登録...")
            step_start = time.time()
            upsert_race.RaceUpsert().upsert_races(races)
            step_time = time.time() - step_start
            st.caption(f"✅ 完了: {progress_utils.format_duration(step_time)}")

            # 出走情報を登録
            st.write("🔄 出走情報を登録...")
            step_start = time.time()
            upsert_entry.EntryUpsert().upsert_entries(entries)
            step_time = time.time() - step_start
            st.caption(f"✅ 完了: {progress_utils.format_duration(step_time)}")

            # 別名補正を適用
            st.write("🔄 別名補正を適用...")
            step_start = time.time()
            apply_alias.AliasApplier().apply_horse_aliases()
            step_time = time.time() - step_start
            st.caption(f"✅ 完了: {progress_utils.format_duration(step_time)}")

            # 指標を計算
            st.write("🔄 指標を計算（この処理が最も時間がかかります）...")
            metric_start = time.time()
            build_horse_metrics.build_all_horse_metrics(incremental=False)
            metric_time = time.time() - metric_start
            st.caption(f"✅ 完了: {progress_utils.format_duration(metric_time)}")

            total_time = time.time() - start_time
            status.update(label="✅ 完了!", state="complete")
            st.success(f"✨ 本番データの投入が完了しました！\n\n総処理時間: {progress_utils.format_duration(total_time)}\n\nページを下にスクロールしてデータを閲覧できます。")

            # キャッシュをクリア
            st.cache_data.clear()

        except Exception as e:
            status.update(label="❌ エラー", state="error")
            st.error(f"エラーが発生しました: {e}")
            import traceback
            st.code(traceback.format_exc())

st.sidebar.markdown("---")

# データ取得
all_dates = queries.get_all_race_dates()

if not all_dates:
    st.warning("📊 データがまだ登録されていません")
    st.info("☝️ サイドバーで年数を選択して、「本番データを投入」をクリックしてください")
    st.stop()

st.sidebar.markdown("---")

# 📚 ヘルプ
st.sidebar.subheader("📚 ヘルプ")
st.sidebar.info(
    """
    **使い方:**
    1. 検索エリアで開催日・会場を選択
    2. 月間/単日ビューを切り替え
    3. レースをクリックして詳細確認
    4. 「モデル学習」でモデルを訓練
    5. 「馬券推奨」で最適配分を確認
    """
)

# ========================
# メインコンテンツ
# ========================

st.title("🐴 競馬レース一覧")

# 検索セクション
st.subheader("🔍 検索")

# 月を抽出してユニークにして、最新順にソート
from datetime import datetime
unique_months = sorted(set(d[:7] for d in all_dates), reverse=True)  # YYYY-MM形式, 最新順

col1, col2 = st.columns([2, 3])

with col1:
    selected_month = st.selectbox(
        "開催月",
        options=unique_months,
        format_func=lambda x: f"{x[:4]}年{x[-2:]}月",
    )

# 選択月の全開催日を取得（最新順）
month_dates = sorted(
    [d for d in all_dates if d.startswith(selected_month)],
    reverse=True
)

# 月内の全開催場を取得
all_courses_in_month = sorted(set(
    course
    for date in month_dates
    for course in (queries.get_courses_by_date(date) or [])
))

with col2:
    if all_courses_in_month:
        selected_courses = st.multiselect(
            "開催場（複数選択可）",
            options=all_courses_in_month,
            default=all_courses_in_month,  # デフォルト全選択
            help="全て選択で全会場のレースを表示"
        )
        if not selected_courses:
            st.error("❌ 最低1つ以上の会場を選択してください")
            st.stop()
    else:
        st.error(f"❌ {selected_month} の開催情報がありません")
        st.stop()

st.markdown("---")

# ========================
# レース表示（3列グリッド）
# ========================

# 会場ごとの色定義
course_colors = {
    course: f"hsl({(i * 360 // len(all_courses_in_month)) % 360}, 70%, 85%)"
    for i, course in enumerate(all_courses_in_month)
}

# 表示対象：選択会場のみのレース情報を取得
display_dates = sorted(
    [d for d in month_dates],
    reverse=True
)

st.markdown(f"### {selected_month[:4]}年{selected_month[-2:]}月 - {', '.join(selected_courses)}")
st.markdown(f"**{len(display_dates)} 日開催**")
st.markdown("---")

if display_dates:
    # 日付ごとのレース情報を整理
    dates_with_races = []
    for race_date in display_dates:
        all_races_for_date = []
        for course in selected_courses:
            races = queries.get_races(race_date, course)
            if races:
                all_races_for_date.extend([(course, race) for race in races])

        if all_races_for_date:
            dates_with_races.append((race_date, all_races_for_date))

    # 3列グリッドで表示
    if dates_with_races:
        for row_start in range(0, len(dates_with_races), 3):
            cols = st.columns(3)
            row_end = min(row_start + 3, len(dates_with_races))

            for col_idx, idx in enumerate(range(row_start, row_end)):
                race_date, all_races_for_date = dates_with_races[idx]

                with cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(f"### 📅 {race_date}")
                        st.markdown(f"**{len(all_races_for_date)} レース**")
                        st.markdown("---")

                        # 会場ごとにグループ化
                        races_by_course = {}
                        for course, race in all_races_for_date:
                            if course not in races_by_course:
                                races_by_course[course] = []
                            races_by_course[course].append(race)

                        # 会場ごとに表示（色分け）
                        for course in selected_courses:
                            if course in races_by_course:
                                # 会場ラベルを色付きで表示
                                st.markdown(
                                    f'<div style="background-color: {course_colors[course]}; '
                                    f'padding: 8px; border-radius: 4px; margin-bottom: 8px;">'
                                    f'<b>{course}</b></div>',
                                    unsafe_allow_html=True
                                )

                                # その会場のレースを表示
                                for race in races_by_course[course]:
                                    race_id = race["race_id"]
                                    st.markdown(f"**R{race['race_no']}** {race.get('title', '無題')}")
                                    st.caption(f"{race['distance_m']}m / {race['surface']}")

                                    if st.button("詳細を見る", key=f"race_{race_id}_{race_date}", use_container_width=True):
                                        st.session_state.selected_race_id = race_id
                                        st.switch_page("pages/8_Race.py")

                                    st.markdown("---")

else:
    st.info(f"📋 {selected_month[:4]}年{selected_month[-2:]}月のレース情報がありません")

# ========================
# フッター
# ========================

st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.caption("✏️ 最終更新は horse_metrics テーブルを参照してください")

with col2:
    if st.button("🔄 キャッシュをクリア"):
        st.cache_data.clear()
        st.rerun()
