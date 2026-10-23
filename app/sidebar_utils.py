"""
Streamlit サイドバーユーティリティ
全ページで統一されたサイドバーを提供
"""

import logging

import streamlit as st
from app import queries, db as db_module

logger = logging.getLogger(__name__)


def render_sidebar():
    """
    統一されたサイドバーをレンダリング
    全ページで共通して使用する
    """
    st.sidebar.title("🐴 競馬DB")
    st.sidebar.markdown("---")

    # 📊 データ統計
    st.sidebar.subheader("📊 データ統計")

    try:
        all_dates = queries.get_all_race_dates()
        all_races = len(all_dates) if all_dates else 0

        # 登録馬数を取得
        try:
            conn = db_module.get_connection(read_only=True)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM horses")
            total_horses = cursor.fetchone()[0]
            conn.close()
        except Exception:
            # 登録馬数が取れない場合もサイドバー自体は表示を継続する
            logger.exception("登録馬数の取得に失敗しました")
            total_horses = 0

        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("開催日数", all_races, help="登録済みの開催日数")
        with col2:
            st.metric("登録馬数", total_horses, help="登録済みの馬の総数")
    except Exception:
        logger.exception("サイドバーのデータ統計取得に失敗しました")
        st.sidebar.warning("⚠️ データベースエラー")

    st.sidebar.markdown("---")

    # 🔍 高速ナビゲーション
    st.sidebar.subheader("🔍 ページ移動")

    st.sidebar.button(
        "🚀 モデル学習",
        use_container_width=True,
        on_click=lambda: st.switch_page("pages/4_ModelTraining.py"),
    )
    st.sidebar.button(
        "🔮 レース予測",
        use_container_width=True,
        on_click=lambda: st.switch_page("pages/6_Prediction_Enhanced.py"),
    )
    st.sidebar.button(
        "💰 馬券推奨",
        use_container_width=True,
        on_click=lambda: st.switch_page("pages/6_Prediction_Enhanced.py"),
    )
    st.sidebar.button(
        "📅 将来レース",
        use_container_width=True,
        on_click=lambda: st.switch_page("pages/2_FutureRaces.py"),
    )
    st.sidebar.button(
        "📊 データエクスポート",
        use_container_width=True,
        on_click=lambda: st.switch_page("pages/3_DataExport.py"),
    )
    st.sidebar.button(
        "🏠 ホーム", use_container_width=True, on_click=lambda: st.switch_page("Home.py")
    )

    st.sidebar.markdown("---")

    # 📚 ヘルプ
    st.sidebar.subheader("📚 ヘルプ")
    st.sidebar.info(
        """
        **使い方:**
        1. ホームで開催日・会場を選択
        2. 月間/単日ビューを切り替え
        3. レースをクリックして詳細確認
        4. 「モデル学習」でモデルを訓練
        5. 「馬券推奨」で最適配分を確認
        """
    )
