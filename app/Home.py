"""
Streamlit アプリケーション - ホームページ
開催日と開催場を選択してレース一覧を表示
"""

import streamlit as st
from pathlib import Path
import sys

# app ディレクトリを sys.path に追加（パッケージインポート対応）
app_dir = Path(__file__).parent
if str(app_dir) not in sys.path:
    sys.path.insert(0, str(app_dir))

from lib import db, queries, charts

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

# 開催日選択
all_dates = queries.get_all_race_dates()

if not all_dates:
    st.warning("📊 データがまだ登録されていません")
    st.info("GitHub Actions またはローカルで初回データ取得を実行してください")
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
    "💡 レース行をクリックして詳細を表示するか、"
    "馬名をクリックして馬詳細ページに移動します"
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
                    st.caption(f"グレード: {race['grade']}")

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

                    # 馬名クリックで詳細ページへ
                    st.caption("馬名をクリックして詳細を確認")

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
