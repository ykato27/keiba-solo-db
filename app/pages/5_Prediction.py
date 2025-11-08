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
from app import backtest

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
    if st.button("🔮 予測", use_container_width=True, disabled=True):
        pass

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

                    # 訓練データ情報
                    st.write(f"📊 訓練データ情報:")
                    st.write(f"  - 総サンプル数: {cv_results['training_samples']}")
                    st.write(f"  - クラス分布: {cv_results['class_distribution']}")

                    # クラス重み付け
                    st.write(f"⚖️ クラス重み付け（不均衡対策）:")
                    for cls_id, weight in cv_results['class_weights'].items():
                        cls_name = {0: "1着", 1: "2-3着", 2: "その他"}.get(int(cls_id), "不明")
                        st.write(f"  - {cls_name}: {weight:.4f}")

                    # 交差検証結果（精度）
                    st.write(f"📊 交差検証結果（精度）:")
                    st.write(f"  - 平均精度: {cv_results['mean_cv_accuracy']:.4f}")
                    st.write(f"  - 標準偏差: {cv_results['std_cv_accuracy']:.4f}")
                    st.write(f"  - 各Fold精度: {[f'{s:.4f}' for s in cv_results['cv_scores']]}")

                    # F1スコア（重要：クラス不均衡への対応指標）
                    st.write(f"📊 交差検証結果（F1スコア）:")
                    st.write(f"  - 平均F1(マクロ): {cv_results['mean_cv_f1']:.4f}")
                    st.write(f"  - 標準偏差: {cv_results['std_cv_f1']:.4f}")
                    st.write(f"  - 各FoldF1: {[f'{s:.4f}' for s in cv_results['cv_f1_scores']]}")

                    # 詳細なFold別情報
                    with st.expander("🔍 Fold別詳細情報"):
                        for fold_info in cv_results['fold_details']:
                            st.write(f"**Fold {fold_info['fold']}**")
                            st.write(f"  - 精度: {fold_info['accuracy']:.4f}")
                            st.write(f"  - F1(マクロ): {fold_info['f1_macro']:.4f}")
                            st.write(f"  - F1(重み付き): {fold_info['f1_weighted']:.4f}")
                            st.write(f"  - 混同行列: {fold_info['confusion_matrix']}")
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

# ========================
# バックテスト
# ========================

st.subheader("📊 バックテスト（過去レースで的中率測定）")

st.markdown("""
選択したモデルを過去のレースで実行し、実際の着順と比較して的中率を計測します。
""")

# バックテスト設定
col1, col2, col3 = st.columns(3)

with col1:
    backtest_start_date = st.date_input(
        "開始日",
        value=None,
        help="バックテスト対象期間の開始日"
    )

with col2:
    backtest_end_date = st.date_input(
        "終了日",
        value=None,
        help="バックテスト対象期間の終了日"
    )

with col3:
    max_sample_races = st.number_input(
        "最大レース数",
        min_value=10,
        max_value=500,
        value=100,
        step=10,
        help="バックテスト対象とするレース数"
    )

if st.button("▶️ バックテストを実行", use_container_width=True, type="secondary"):
    if not backtest_start_date or not backtest_end_date:
        st.error("❌ 開始日と終了日を指定してください")
    elif backtest_end_date < backtest_start_date:
        st.error("❌ 終了日が開始日より前です")
    else:
        with st.status("バックテスト実行中...", expanded=True) as status:
            try:
                if model_choice == "LightGBM（推奨）":
                    st.write("📊 バックテスト実行中...")

                    # バックテストランナーを取得
                    bt_runner = backtest.get_backtest_runner()

                    # バックテスト実行
                    backtest_results = bt_runner.run_backtest(
                        start_date=backtest_start_date.strftime("%Y-%m-%d"),
                        end_date=backtest_end_date.strftime("%Y-%m-%d"),
                        sample_races=max_sample_races
                    )

                    status.update(label="✅ 完了!", state="complete")

                    # 結果表示
                    st.subheader("🎯 バックテスト結果")

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(
                            "対象レース数",
                            backtest_results['total_races']
                        )
                    with col2:
                        st.metric(
                            "総予測数",
                            backtest_results['total_predictions']
                        )
                    with col3:
                        st.metric(
                            "期間",
                            backtest_results['date_range']
                        )

                    st.markdown("---")

                    # 的中率
                    col1, col2 = st.columns(2)

                    with col1:
                        st.write("**1着予測の的中率**")
                        st.metric(
                            "1着的中数",
                            f"{backtest_results['win_hits']}",
                            f"{backtest_results['win_accuracy']:.2f}%"
                        )

                    with col2:
                        st.write("**複勝予測の的中率**")
                        st.metric(
                            "2-3着的中数",
                            f"{backtest_results['place_hits']}",
                            f"{backtest_results['place_accuracy']:.2f}%"
                        )

                    st.markdown("---")

                    # 期待値計算
                    st.write("**期待値分析**")

                    col1, col2 = st.columns(2)

                    with col1:
                        assumed_odds_win = st.number_input(
                            "仮定する1着オッズ",
                            min_value=1.0,
                            value=5.0,
                            step=0.5
                        )

                    with col2:
                        assumed_odds_place = st.number_input(
                            "仮定する複勝オッズ",
                            min_value=1.0,
                            value=2.0,
                            step=0.1
                        )

                    # 期待値を計算
                    ev_results = bt_runner.calculate_expected_value(
                        backtest_results,
                        assumed_odds_win=assumed_odds_win,
                        assumed_odds_place=assumed_odds_place
                    )

                    if 'error' not in ev_results:
                        col1, col2 = st.columns(2)

                        with col1:
                            st.write("**1着投票の期待値**")
                            st.metric(
                                "勝率",
                                f"{ev_results['win_win_rate']:.2%}",
                                f"EV: {ev_results['win_expected_value']:.3f}"
                            )

                        with col2:
                            st.write("**複勝投票の期待値**")
                            st.metric(
                                "的中率",
                                f"{ev_results['place_hit_rate']:.2%}",
                                f"EV: {ev_results['place_expected_value']:.3f}"
                            )

                        st.info(f"💡 {ev_results['recommendation']}")

                    # 詳細レース情報
                    with st.expander("🔍 レース別詳細"):
                        for race_detail in backtest_results['race_details'][:10]:
                            st.write(f"**{race_detail['race_date']} {race_detail['course']} ({race_detail['distance_m']}m)**")

                            for hit in race_detail['hits']:
                                status_emoji = "✅" if hit['is_win_hit'] else ("🟢" if hit['is_place_hit'] else "❌")
                                st.write(f"{status_emoji} {hit['horse_name']}: 予想{hit['predicted_rank']}位 → 実際{hit['actual_finish']}位")

                            st.divider()
                else:
                    st.warning("⚠️ Random Forestではバックテスト機能は未対応です")

            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"バックテストエラー: {e}")
                import traceback
                st.code(traceback.format_exc())

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
