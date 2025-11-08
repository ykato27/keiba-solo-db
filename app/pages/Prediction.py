"""
Streamlit アプリケーション - レース予測ページ（拡張版）
複数の機械学習モデルを使用したレース結果の予測分析
"""

import streamlit as st
import sys
from pathlib import Path

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import queries
from app import prediction_model as pm
from app import prediction_model_lightgbm as pml

st.set_page_config(
    page_title="レース予測 - 競馬データベース",
    page_icon="🐴",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("🔮 レース予測")

st.markdown("機械学習を使用したレース結果の予測分析")

# ナビゲーションメニュー
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏇 競馬データ", use_container_width=True):
        st.switch_page("Home.py")

with col2:
    if st.button("🔮 予測", use_container_width=True, disabled=True):
        pass

with col3:
    if st.button("📊 エクスポート", use_container_width=True):
        st.switch_page("pages/DataExport.py")

st.markdown("---")

# ========================
# モデルの選択と管理
# ========================

st.subheader("📊 予測モデルの選択")

# モデル選択
model_choice = st.radio(
    "使用するモデルを選択",
    options=["LightGBM（推奨）", "ランダムフォレスト"],
    help="LightGBMの方が高精度ですが、データ量が多い場合に有効です"
)

st.markdown("---")

# 選択したモデルを初期化
if model_choice == "LightGBM（推奨）":
    model = pml.get_advanced_prediction_model()
    model_type_display = "LightGBM + TimeSeriesSplit"
else:
    model = pm.get_prediction_model()
    model_type_display = "Random Forest"

model_info = model.get_model_info()

# モデル情報の表示
col1, col2, col3, col4 = st.columns(4)

with col1:
    status = "✅ 訓練済み" if model_info['is_trained'] else "⚠️ 未訓練"
    st.metric("ステータス", status)

with col2:
    st.metric("モデル", model_info.get('model_type', model_type_display))

with col3:
    st.metric("特徴量数", model_info['n_features'])

with col4:
    st.metric("バージョン", "v2.0（改善版）")

st.markdown("---")

# モデルの訓練
if not model_info['is_trained']:
    st.warning("⚠️ 選択したモデルがまだ訓練されていません")

    if st.button("🚀 モデルを訓練する", use_container_width=True, type="primary"):
        with st.status("モデル訓練中...", expanded=True) as status:
            try:
                if model_choice == "LightGBM（推奨）":
                    st.write("⏳ TimeSeriesSplitで交差検証中...")
                    cv_results = model.train_with_cross_validation()

                    st.write(f"📊 交差検証結果:")
                    st.write(f"  - 平均精度: {cv_results['mean_cv_accuracy']:.4f}")
                    st.write(f"  - 標準偏差: {cv_results['std_cv_accuracy']:.4f}")
                    st.write(f"  - 各Fold精度: {[f'{s:.4f}' for s in cv_results['cv_scores']]}")
                else:
                    st.write("訓練データを構築中...")
                    model.train()

                status.update(label="✅ 完了!", state="complete")
                st.success("✨ モデルの訓練が完了しました！")
                st.balloons()
                st.rerun()
            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"訓練エラー: {e}")
                import traceback
                st.code(traceback.format_exc())

    st.stop()

# 訓練済みモデルの特徴量重要度を表示
if model_choice == "LightGBM（推奨）":
    with st.expander("📈 特徴量の重要度（Top 20）"):
        importances = model.get_feature_importance()
        if importances:
            # 上位20個を表示
            top_features = importances[:20]
            feature_names = [f[0] for f in top_features]
            feature_values = [f[1] for f in top_features]

            # グラフ表示
            import pandas as pd
            df_importance = pd.DataFrame({
                '特徴量': feature_names,
                '重要度': feature_values
            })
            st.bar_chart(df_importance.set_index('特徴量'))

            # テーブル表示
            st.dataframe(df_importance, use_container_width=True, hide_index=True)

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

    # レース情報を取得
    race = next((r for r in races if r['race_id'] == selected_race_id), None)
    race_info = {
        'distance_m': race.get('distance_m') if race else 0,
        'surface': race.get('surface') if race else '',
    } if race else None

    # 予測実行
    with st.status("予測中...", expanded=True) as status:
        st.write(f"📊 {len(horse_ids)}頭の馬を分析中...")
        prediction_results = model.predict_race_order(horse_ids, race_info=race_info)
        status.update(label="✅ 完了!", state="complete")

    # 予測結果表示
    if 'predictions' in prediction_results:
        predictions = prediction_results['predictions']

        st.subheader("📋 予測結果")

        # モデルの使用情報表示
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("使用モデル", prediction_results.get('model_type', 'Unknown'))
        with col2:
            st.metric("分析対象数", prediction_results.get('total_horses', len(predictions)))
        with col3:
            st.metric("ランク", f"Top {len(predictions)}")

        st.markdown("---")

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
    💡 **予測モデルについて**

    ### LightGBM（推奨）
    - **特徴量**：60+個の複合特徴量
      * WHO：馬の基本特性（出走経験、成績メトリクス）
      * WHEN：距離別・馬場別成績
      * RACE：距離タイプ、馬場タイプ
      * ENTRY：体重、休み期間、年齢
      * PEDIGREE：血統スコア
    - **モデル**：LightGBM / GradientBoosting
    - **交差検証**：TimeSeriesSplit（未来情報リーク防止）
    - **予測目標**：1着、2-3着、その他

    ### ランダムフォレスト（基本版）
    - **特徴量**：11個の基本特徴量
    - **モデル**：ランダムフォレスト分類器
    - **予測目標**：1着、2-3着、その他

    ### 注意事項
    実際のレース予測には、天気、馬場状態、騎手の調子など、
    多くの要因が影響するため、参考情報としてご利用ください。
    """
)

if st.button("🔄 キャッシュをクリア"):
    st.cache_data.clear()
    st.rerun()
