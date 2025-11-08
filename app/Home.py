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

st.sidebar.title("🐴 競馬データベース")
st.sidebar.markdown("---")

# ナビゲーションメニュー
st.sidebar.subheader("📋 メニュー")

col1, col2, col3 = st.sidebar.columns(3)

with col1:
    if st.button("🏠 ホーム", use_container_width=True, disabled=True):
        pass

with col2:
    if st.button("📅 将来レース", use_container_width=True):
        st.switch_page("pages/2_FutureRaces.py")

with col3:
    if st.button("📊 エクスポート", use_container_width=True):
        st.switch_page("pages/3_DataExport.py")

st.sidebar.markdown("---")

# 管理者パネル
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

# 予測ページへのリンク
st.sidebar.subheader("🔮 レース予測")
if st.sidebar.button("予測ページへ移動", use_container_width=True):
    st.switch_page("pages/Prediction.py")

st.sidebar.markdown("---")

# 開催日選択
all_dates = queries.get_all_race_dates()

if not all_dates:
    st.warning("📊 データがまだ登録されていません")
    st.info("☝️ サイドバーで年数を選択して、「本番データを投入」をクリックしてください")
    st.stop()

selected_date = st.sidebar.selectbox(
    "開催日を選択",
    options=all_dates,
    format_func=lambda x: f"{x} ({len(queries.get_courses_by_date(x))}開催)",
)

# 開催場選択
courses = queries.get_courses_by_date(selected_date)

if not courses:
    st.error(f"❌ {selected_date} の開催情報が見つかりません")
    st.stop()

selected_course = st.sidebar.selectbox(
    "開催場を選択",
    options=courses,
)

st.sidebar.markdown("---")

# 統計情報
st.sidebar.subheader("📈 統計")
total_races = len(all_dates)
st.sidebar.metric("開催日数", total_races)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 「詳細」ボタンでレース詳細ページに移動します"
)

# ========================
# メインコンテンツ
# ========================

st.title("🐴 競馬レース一覧")

st.markdown(f"""
### {selected_date} - {selected_course}
""")

# レース一覧を取得
races = queries.get_races(selected_date, selected_course)

if not races:
    st.warning(f"レース情報がありません")
else:
    st.markdown(f"**{len(races)} レース開催**")
    st.markdown("---")

    # レーストabs
    for race in races:
        race_id = race["race_id"]

        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([1, 2, 2, 1])

            with col1:
                st.markdown(f"### R{race['race_no']}")

            with col2:
                st.markdown(f"**{race.get('title', '無題')}**")
                st.caption(f"{race['distance_m']}m / {race['surface']}")

            with col3:
                if race.get('going'):
                    st.caption(f"馬場: {race['going']}")
                if race.get('grade'):
                    st.caption(f"クラス: {race['grade']}")

            with col4:
                if st.button("詳細", key=f"race_{race_id}"):
                    st.session_state.selected_race_id = race_id
                    st.switch_page("pages/Race.py")

            # 出走馬簡易表示
            with st.expander("出走馬", expanded=False):
                entries = queries.get_race_entries_with_metrics(race_id)

                if entries:
                    # テーブル表示用データ
                    table_data = []
                    for entry in entries:
                        table_data.append({
                            "馬番": entry.get("horse_no"),
                            "馬名": entry.get("horse_name"),
                            "騎手": entry.get("jockey_name", "-"),
                            "斤量": entry.get("weight_carried", "-"),
                            "勝率": f"{(entry.get('win_rate', 0) or 0) * 100:.1f}%",
                            "人気": entry.get("popularity", "-"),
                        })

                    st.dataframe(
                        table_data,
                        use_container_width=True,
                        hide_index=True,
                    )

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
