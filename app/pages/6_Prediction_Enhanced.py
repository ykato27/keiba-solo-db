"""
Streamlit アプリケーション - レース予測ページ（拡張版）

フロー:
  1. バックテスト（過去データで検証）
  2. モデル訓練
  3. 将来レースの予測
  4. 最適馬券配分の推奨
"""

import streamlit as st
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # プロジェクトルート（app/legacy の解決用）

from app import queries, prediction_model_lightgbm as pml
from app import backtest as bt
from app.betting_optimizer import BettingOptimizer

st.set_page_config(
    page_title="レース予測 - 競馬データベース",
    page_icon="🐴",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("🔮 レース予測 & 馬券配分")
st.markdown("バックテスト → モデル訓練 → 将来レース予測 → 最適馬券配分")

# ナビゲーション
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
    if st.button("💰 推奨", use_container_width=True, disabled=True):
        pass
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
# Tab 1: バックテスト
# ========================

tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 バックテスト", "🚀 モデル訓練", "🎯 将来レース予測", "💰 馬券配分推奨"]
)

with tab1:
    st.subheader("📊 過去レースでモデルを検証")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "開始日", value=datetime.now().date() - timedelta(days=90), help="バックテスト開始日"
        )

    with col2:
        end_date = st.date_input("終了日", value=datetime.now().date(), help="バックテスト終了日")

    if st.button("🔍 バックテストを実行", type="primary", use_container_width=True):
        with st.status("バックテスト実行中...", expanded=True) as status:
            try:
                # モデル初期化
                model = pml.get_advanced_prediction_model()

                if not model.is_trained:
                    st.warning("⚠️ モデルがまだ訓練されていません。先にモデル訓練を実行してください")
                    st.stop()

                st.write(f"📅 期間: {start_date} ～ {end_date}")

                # バックテスト実行
                runner = bt.BacktestRunner(model)
                results = runner.run_backtest(start_date=str(start_date), end_date=str(end_date))

                status.update(label="✅ 完了", state="complete")

                # 結果表示
                st.subheader("📈 バックテスト結果")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("総レース数", results.get("total_races", 0))

                with col2:
                    st.metric("1着予測 的中率", f"{results.get('win_accuracy', 0):.1%}")

                with col3:
                    st.metric("2-3着予測 的中率", f"{results.get('place_accuracy', 0):.1%}")

                with col4:
                    st.metric("総予測数", results.get("total_predictions", 0))

                # 詳細結果
                if results.get("race_details"):
                    with st.expander("詳細結果を表示", expanded=False):
                        st.dataframe(
                            pd.DataFrame(results["race_details"]), use_container_width=True
                        )

            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"バックテスト実行エラー: {e}")

# ========================
# Tab 2: モデル訓練
# ========================

with tab2:
    st.subheader("🚀 機械学習モデルを訓練")

    col1, col2 = st.columns(2)

    with col1:
        model_choice = st.radio(
            "モデル選択",
            options=["LightGBM（推奨）", "ランダムフォレスト"],
            help="LightGBMが推奨（精度が高い）",
        )

    with col2:
        # 訓練データ期間
        train_days = st.slider(
            "訓練データ期間（日数）",
            min_value=30,
            max_value=365,
            value=90,
            help="過去N日間のデータで訓練",
        )

    if st.button("📚 モデルを訓練", type="primary", use_container_width=True):
        with st.status("モデル訓練中...", expanded=True) as status:
            try:
                # モデル選択
                if model_choice == "LightGBM（推奨）":
                    model = pml.AdvancedRacePredictionModel()
                else:
                    from legacy import prediction_model as pm

                    model = pm.RacePredictionModel()

                st.write(f"📊 過去 {train_days} 日間のデータで訓練を開始...")

                # 訓練データ構築
                X, y, race_dates = model.build_training_data_with_cv()

                st.write(f"✅ 訓練データ: {len(X)} サンプル")
                st.write(f"✅ 特徴量数: {X.shape[1]}")

                # 訓練実行
                st.write("🤖 モデル訓練中...")
                results = model.train()

                st.write(f"✅ 訓練完了")

                status.update(label="✅ 完了", state="complete")

                # 結果表示
                st.subheader("📊 訓練結果")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "平均精度",
                        f"{results.get('mean_cv_accuracy', 0):.2%}",
                        delta=f"±{results.get('std_cv_accuracy', 0):.2%}",
                    )

                with col2:
                    st.metric("平均 F1 スコア", f"{results.get('mean_cv_f1', 0):.4f}")

                with col3:
                    st.metric("モデル", model_choice.split("（")[0])

                # Fold詳細
                if results.get("fold_info"):
                    with st.expander("Fold別詳細を表示", expanded=False):
                        fold_df = pd.DataFrame(results["fold_info"])
                        st.dataframe(fold_df, use_container_width=True)

                st.success("✨ モデルが正常に訓練されました")

            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"訓練エラー: {e}")

# ========================
# Tab 3: 将来レース予測
# ========================

with tab3:
    st.subheader("🎯 将来のレースを予測")
    st.info("💡 このタブは、スクレイピングで取得した『今日以降のレース』を予測します")

    # レース選択
    try:
        from datetime import datetime, timedelta

        # 今日の日付を取得
        today = datetime.now().date()
        today_str = today.strftime("%Y-%m-%d")

        # 全開催日を取得
        all_dates = queries.get_all_race_dates()

        if all_dates:
            # 今日以降のレースを取得
            future_races_list = []
            for date in sorted(all_dates):  # 昇順（未来）でソート
                if date >= today_str:  # 今日以降のみ
                    courses = queries.get_courses_by_date(date)
                    if courses:
                        for course in courses:
                            races = queries.get_races(date, course)
                            if races:
                                for race in races:
                                    future_races_list.append(
                                        (
                                            race["race_id"],
                                            date,
                                            course,
                                            race["race_no"],
                                            race.get("title", "無題"),
                                        )
                                    )

            if future_races_list:
                race_options = {f"{r[1]} - {r[2]} {r[3]}R {r[4]}": r[0] for r in future_races_list}

                selected_race_display = st.selectbox(
                    "レースを選択", options=race_options.keys(), help="予測対象のレースを選択"
                )

                if selected_race_display:
                    race_id = race_options[selected_race_display]

                    if st.button("🔮 予測を実行", type="primary", use_container_width=True):
                        with st.status("予測実行中...", expanded=True) as status:
                            try:
                                # モデル初期化
                                model = pml.get_advanced_prediction_model()

                                if not model.is_trained:
                                    st.warning("⚠️ モデルがまだ訓練されていません")
                                    st.stop()

                                # 出走馬を取得
                                entries = queries.get_race_entries(race_id)

                                if not entries:
                                    st.error("このレースの出走馬情報が見つかりません")
                                    st.stop()

                                st.write(f"📊 {len(entries)} 頭の予測を実行中...")

                                # 予測
                                predictions = []
                                for entry in entries:
                                    try:
                                        pred = model.predict(
                                            race_id=race_id,
                                            horse_id=entry.get("horse_id"),
                                            entry_info=entry,
                                        )
                                        predictions.append(pred)
                                    except Exception as e:
                                        st.warning(f"予測エラー: {e}")
                                        continue

                                status.update(label="✅ 完了", state="complete")

                                st.subheader("📈 予測結果")

                                # 予測結果をDataFrameに
                                pred_df = pd.DataFrame(
                                    [
                                        {
                                            "馬名": p.get("horse_name"),
                                            "1着確率": f"{p.get('win_prob', 0):.1%}",
                                            "2-3着確率": f"{p.get('place_prob', 0):.1%}",
                                            "その他確率": f"{p.get('other_prob', 0):.1%}",
                                        }
                                        for p in predictions
                                    ]
                                )

                                st.dataframe(pred_df, use_container_width=True)

                                # 将来のTab4へデータを渡す
                                st.session_state.latest_predictions = predictions
                                st.session_state.latest_race_id = race_id

                                st.info("💡 「馬券配分推奨」タブで最適な配分を確認できます")

                            except Exception as e:
                                status.update(label="❌ エラー", state="error")
                                st.error(f"予測エラー: {e}")

            else:
                st.info("📋 今日以降のレース情報がまだ登録されていません")
                st.write("💡 「将来レース」ページからスクレイピングでレース情報を取得してください")

    except Exception as e:
        st.error(f"レース取得エラー: {e}")

# ========================
# Tab 4: 馬券配分推奨
# ========================

with tab4:
    st.subheader("💰 期待収益を最大化する馬券配分")

    st.info(
        """
        🎯 **Kelly基準** を使用した最適配分

        Kelly基準は、確率ゲームで資金を最大化する数学的手法です。
        """
    )

    # 予測がない場合
    if "latest_predictions" not in st.session_state:
        st.warning("⚠️ 先に「将来レース予測」タブで予測を実行してください")
        st.stop()

    predictions = st.session_state.latest_predictions

    # 予算選択
    st.subheader("💵 投資予算シナリオ")

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        budget_1000 = st.checkbox("1,000円", value=True)
    with col2:
        budget_5000 = st.checkbox("5,000円", value=True)
    with col3:
        budget_10000 = st.checkbox("10,000円", value=True)
    with col4:
        budget_50000 = st.checkbox("50,000円", value=False)
    with col5:
        budget_100000 = st.checkbox("100,000円", value=False)

    # 選択された予算
    selected_budgets = []
    if budget_1000:
        selected_budgets.append(1000)
    if budget_5000:
        selected_budgets.append(5000)
    if budget_10000:
        selected_budgets.append(10000)
    if budget_50000:
        selected_budgets.append(50000)
    if budget_100000:
        selected_budgets.append(100000)

    if st.button("🎯 最適配分を計算", type="primary", use_container_width=True):
        with st.status("計算中...", expanded=True) as status:
            try:
                optimizer = BettingOptimizer()

                # 予測データをフォーマット
                pred_data = [
                    {
                        "horse_name": p.get("horse_name"),
                        "win_probability": p.get("win_prob", 0),
                        "expected_odds": 3.0,  # デフォルト（実際はオッズを使用）
                    }
                    for p in predictions
                ]

                # 各予算シナリオで最適化
                for budget in selected_budgets:
                    st.subheader(f"💵 予算: {budget:,}円")

                    recommendations = optimizer.optimize_portfolio(
                        pred_data, total_budget=budget, min_probability=0.05
                    )

                    if not recommendations:
                        st.info("推奨配分がありません")
                        continue

                    # 推奨表を作成
                    rec_data = []
                    for rec in recommendations[:5]:  # 上位5つ
                        rec_data.append(
                            {
                                "馬名": rec.horse_name,
                                "勝つ確率": f"{rec.win_probability:.1%}",
                                "配分割合": f"{rec.kelly_fraction:.1%}",
                                "推奨賭金": f"{rec.kelly_bet:.0f}円",
                                "期待ROI": f"{rec.expected_roi:.2f}%",
                                "期待利益": f"{rec.expected_profit:.0f}円",
                            }
                        )

                    rec_df = pd.DataFrame(rec_data)
                    st.dataframe(rec_df, use_container_width=True)

                    # ポートフォリオ統計
                    stats = optimizer.calculate_portfolio_stats(recommendations)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("総投資額", f"{stats.get('total_bet', 0):,.0f}円")
                    with col2:
                        st.metric(
                            "期待利益",
                            f"{stats.get('expected_total_profit', 0):,.0f}円",
                            delta=f"{stats.get('expected_total_roi', 0):.2f}%",
                        )
                    with col3:
                        st.metric("対象馬数", stats.get("num_bets", 0))

                    st.markdown("---")

                status.update(label="✅ 完了", state="complete")

            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"計算エラー: {e}")
