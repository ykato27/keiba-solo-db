"""
Streamlit アプリケーション - モデル学習ページ

フロー:
  1. バックテスト（過去データで検証）
  2. モデル訓練（機械学習モデルを学習）

注意: 予測は別ページ（Prediction, Prediction_Enhanced）で実施
"""

import streamlit as st
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import queries, prediction_model_lightgbm as pml
from app import backtest as bt

st.set_page_config(
    page_title="モデル学習 - 競馬データベース",
    page_icon="🚀",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("🚀 モデル学習")
st.markdown("バックテスト → モデル訓練")

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
    if st.button("🚀 学習", use_container_width=True, disabled=True):
        pass
with col5:
    if st.button("🔮 予測", use_container_width=True):
        st.switch_page("pages/5_Prediction.py")
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
# Tab 1: バックテスト
# ========================

tab1, tab2 = st.tabs([
    "📊 バックテスト",
    "🚀 モデル訓練",
])

with tab1:
    st.subheader("📊 過去レースでモデルを検証")

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "開始日",
            value=datetime.now().date() - timedelta(days=90),
            help="バックテスト開始日"
        )

    with col2:
        end_date = st.date_input(
            "終了日",
            value=datetime.now().date(),
            help="バックテスト終了日"
        )

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
                results = runner.run_backtest(
                    start_date=str(start_date),
                    end_date=str(end_date)
                )

                status.update(label="✅ 完了", state="complete")

                # 結果表示
                st.subheader("📈 バックテスト結果")

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "総レース数",
                        results.get('total_races', 0)
                    )

                with col2:
                    st.metric(
                        "1着予測 的中率",
                        f"{results.get('win_accuracy', 0):.1%}"
                    )

                with col3:
                    st.metric(
                        "2-3着予測 的中率",
                        f"{results.get('place_accuracy', 0):.1%}"
                    )

                with col4:
                    st.metric(
                        "総予測数",
                        results.get('total_predictions', 0)
                    )

                # 詳細結果
                if results.get('race_details'):
                    with st.expander("詳細結果を表示", expanded=False):
                        st.dataframe(
                            pd.DataFrame(results['race_details']),
                            use_container_width=True
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
            help="LightGBMが推奨（精度が高い）"
        )

    with col2:
        # 訓練データ期間
        train_days = st.slider(
            "訓練データ期間（日数）",
            min_value=30,
            max_value=365,
            value=90,
            help="過去N日間のデータで訓練"
        )

    if st.button("📚 モデルを訓練", type="primary", use_container_width=True):
        with st.status("モデル訓練中...", expanded=True) as status:
            try:
                # モデル選択
                if model_choice == "LightGBM（推奨）":
                    model = pml.AdvancedRacePredictionModel()
                else:
                    from app import prediction_model as pm
                    model = pm.RacePredictionModel()

                st.write(f"📊 過去 {train_days} 日間のデータで訓練を開始...")

                # 訓練データ構築
                X, y, race_dates = model.build_training_data_with_cv()

                st.write(f"✅ 訓練データ: {len(X) if X is not None else 0} サンプル")
                if X is not None:
                    st.write(f"✅ 特徴量数: {X.shape[1]}")

                # 訓練実行
                st.write("🤖 モデル訓練中...")
                results = model.train_with_cross_validation()

                st.write(f"✅ 訓練完了")

                status.update(label="✅ 完了", state="complete")

                # 結果表示
                st.subheader("📊 訓練結果")

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric(
                        "平均精度",
                        f"{results.get('mean_cv_accuracy', 0):.2%}",
                        delta=f"±{results.get('std_cv_accuracy', 0):.2%}"
                    )

                with col2:
                    st.metric(
                        "平均 F1 スコア",
                        f"{results.get('mean_cv_f1', 0):.4f}"
                    )

                with col3:
                    st.metric(
                        "モデル",
                        model_choice.split("（")[0]
                    )

                # データリーク検証結果
                if 'data_leakage_validation' in results:
                    st.subheader("🔍 データリーク検証結果")
                    validation = results['data_leakage_validation']

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric(
                            "総Fold数",
                            validation.get('total_folds', 0)
                        )
                    with col2:
                        st.metric(
                            "✅ 有効なFold",
                            validation.get('summary', {}).get('total_valid_folds', 0)
                        )
                    with col3:
                        status_text = "✅ 合格" if validation.get('all_valid') else "⚠️ 警告有り"
                        st.metric("全体判定", status_text)

                    # 詳細表示
                    with st.expander("詳細な検証結果を表示", expanded=False):
                        for fold in validation.get('folds', []):
                            st.write(f"**Fold {fold.get('fold_num')}**")
                            st.write(f"  訓練期間: {fold['train_date_range'][0]} ～ {fold['train_date_range'][1]}")
                            st.write(f"  テスト期間: {fold['test_date_range'][0]} ～ {fold['test_date_range'][1]}")
                            if fold.get('days_gap') is not None:
                                st.write(f"  時間ギャップ: {fold['days_gap']}日")
                            st.write(f"  判定: {'✅ OK' if fold['is_valid'] else '❌ NG'}")

                # Fold詳細
                if results.get('fold_details'):
                    with st.expander("Fold別詳細を表示", expanded=False):
                        fold_df = pd.DataFrame(results['fold_details'])
                        st.dataframe(fold_df, use_container_width=True)

                # クラス分布
                if results.get('class_distribution'):
                    st.subheader("📊 クラス分布")
                    class_dist = results['class_distribution']
                    dist_data = {
                        'クラス': ['1着', '複勝(2-3着)', 'その他'],
                        'サンプル数': [
                            class_dist.get(0, 0),
                            class_dist.get(1, 0),
                            class_dist.get(2, 0),
                        ]
                    }
                    dist_df = pd.DataFrame(dist_data)
                    st.bar_chart(dist_df.set_index('クラス'))

                st.success("✨ モデルが正常に訓練されました")

            except Exception as e:
                status.update(label="❌ エラー", state="error")
                st.error(f"訓練エラー: {e}")
                import traceback
                st.code(traceback.format_exc())

# 説明セクション
st.markdown("---")
st.markdown("""
### 📚 モデル学習について

**バックテスト**
- 過去のレースデータでモデルの予測精度を検証します
- 指定した期間のレースで、モデルの的中率を測定します

**モデル訓練**
- 機械学習モデルを訓練します
- TimeSeriesSplit を使用して、データリークを防ぎながら訓練します
- 複数のメトリクス（精度, F1スコア）で評価します

**注意**
- モデル訓練には数分かかる場合があります
- 訓練後は、別ページ（Prediction, Prediction Enhanced）で予測を実施してください
""")
