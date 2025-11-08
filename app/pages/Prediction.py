"""
Streamlit アプリケーション - レース予測ページ
機械学習を用いたレース結果の予測
"""

import streamlit as st
import sys
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

import queries
import prediction_model as pm

st.set_page_config(
    page_title="レース予測 - 競馬データベース",
    page_icon="🐴",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("🔮 レース予測")

col1, col2 = st.columns([3, 1])

with col1:
    st.markdown("機械学習を使用したレース結果の予測分析")

with col2:
    if st.button("← 戻る"):
        st.switch_page("Home.py")

st.markdown("---")

# ========================
# モデルの管理
# ========================

st.subheader("📊 予測モデルの管理")

model = pm.get_prediction_model()
model_info = model.get_model_info()

col1, col2, col3 = st.columns(3)

with col1:
    status = "✅ 訓練済み" if model_info['is_trained'] else "⚠️ 未訓練"
    st.metric("モデルステータス", status)

with col2:
    st.metric("モデルタイプ", "ランダムフォレスト")

with col3:
    st.metric("特徴量数", model_info['n_features'])

st.markdown("---")

# モデルの訓練
if not model_info['is_trained']:
    st.warning("⚠️ 予測モデルがまだ訓練されていません")

    if st.button("🚀 モデルを訓練する", use_container_width=True):
        with st.status("モデル訓練中...", expanded=True) as status:
            try:
                st.write("訓練データを構築中...")
                model.train()
                status.update(label="✅ 完了!", state="complete")
                st.success("✨ モデルの訓練が完了しました！")
                st.rerun()
            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"訓練エラー: {e}")

    st.stop()

# ========================
# レース選択と予測
# ========================

st.subheader("🎯 レース予測")

# 開催日選択
all_dates = queries.get_all_race_dates()

if not all_dates:
    st.warning("📊 データがありません")
    st.stop()

selected_date = st.selectbox(
    "開催日を選択",
    options=all_dates,
    format_func=lambda x: f"{x} ({len(queries.get_courses_by_date(x))}開催)",
)

# 開催場選択
courses = queries.get_courses_by_date(selected_date)

if not courses:
    st.error(f"❌ {selected_date} の開催情報が見つかりません")
    st.stop()

selected_course = st.selectbox(
    "開催場を選択",
    options=courses,
)

# レース選択
races = queries.get_races(selected_date, selected_course)

if not races:
    st.warning(f"レース情報がありません")
    st.stop()

race_options = {
    race['race_id']: f"R{race['race_no']} - {race.get('title', '無題')} ({race['distance_m']}m / {race['surface']})"
    for race in races
}

selected_race_id = st.selectbox(
    "レースを選択",
    options=list(race_options.keys()),
    format_func=lambda x: race_options[x],
)

st.markdown("---")

# ========================
# 予測実行
# ========================

if st.button("🔮 予測を実行", use_container_width=True, type="primary"):
    # 選択されたレースの出走馬を取得
    entries = queries.get_race_entries_with_metrics(selected_race_id)

    if not entries:
        st.error("出走馬情報が見つかりません")
        st.stop()

    horse_ids = [e['horse_id'] for e in entries if e['horse_id']]

    if not horse_ids:
        st.error("有効な馬IDが見つかりません")
        st.stop()

    # 予測実行
    with st.status("予測中...", expanded=True) as status:
        st.write(f"📊 {len(horse_ids)}頭の馬を分析中...")
        prediction_results = model.predict_race_order(horse_ids)
        status.update(label="✅ 完了!", state="complete")

    # 予測結果表示
    if 'predictions' in prediction_results:
        predictions = prediction_results['predictions']

        st.subheader("📋 予測結果")

        # テーブル表示用データ
        table_data = []
        for rank, pred in enumerate(predictions, 1):
            table_data.append({
                "順位": f"#{rank}",
                "馬名": pred['horse_name'],
                "1着の可能性": f"{pred['win_probability']:.1f}%",
                "2-3着の可能性": f"{pred['place_probability']:.1f}%",
                "その他": f"{pred['other_probability']:.1f}%",
                "確度": f"{pred['confidence']:.1f}%",
            })

        st.dataframe(table_data, use_container_width=True, hide_index=True)

        st.markdown("---")

        # 詳細分析
        st.subheader("📊 詳細分析")

        tab1, tab2, tab3 = st.tabs(["1着可能性", "2-3着可能性", "確度"])

        with tab1:
            st.bar_chart(
                {
                    pred['horse_name']: pred['win_probability']
                    for pred in predictions[:10]
                },
                height=400,
            )
            st.caption("1着の可能性が高い上位10頭")

        with tab2:
            st.bar_chart(
                {
                    pred['horse_name']: pred['place_probability']
                    for pred in predictions[:10]
                },
                height=400,
            )
            st.caption("2-3着の可能性が高い上位10頭")

        with tab3:
            st.bar_chart(
                {
                    pred['horse_name']: pred['confidence']
                    for pred in predictions[:10]
                },
                height=400,
            )
            st.caption("予測の確度が高い上位10頭")

    else:
        st.error(f"予測エラー: {prediction_results.get('error', '不明なエラー')}")

st.markdown("---")

# 情報
st.info(
    """
    💡 **予測について**

    このモデルは過去のレース結果から学習した機械学習モデルを使用しています。

    - 特徴量：馬の勝率、連対率、複勝率、近走指数、距離別成績、馬場別成績
    - モデル：ランダムフォレスト分類器
    - 予測目標：1着、2-3着、その他

    実際のレース予測には、天気、馬場状態、騎手の調子など、
    多くの要因が影響するため、参考情報としてご利用ください。
    """
)

if st.button("🔄 キャッシュをクリア"):
    st.cache_data.clear()
    st.rerun()
