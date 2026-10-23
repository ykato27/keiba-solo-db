"""
Streamlit アプリケーション - 将来レース情報ページ
JRA公式サイトから今週末、来週末のレース情報をスクレイピング
"""

import streamlit as st
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# パス設定
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import queries, db
from etl import upsert_race, upsert_entry, apply_alias
from metrics import build_horse_metrics

# 直接import（キャッシュ問題回避）
from scraper.fetch_future_races import fetch_upcoming_races, fetch_multiple_race_cards

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="将来レース情報 - 競馬データベース",
    page_icon="📅",
    layout="wide",
)

# ========================
# ページヘッダー
# ========================

st.title("📅 将来レース情報")

st.markdown("JRA公式サイトから今週末・来週末のレース情報をスクレイピング")

# ナビゲーションメニュー
col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)

with col1:
    if st.button("🏠 ホーム", use_container_width=True):
        st.switch_page("Home.py")

with col2:
    if st.button("📅 将来レース", use_container_width=True, disabled=True):
        pass

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
# 設定パネル
# ========================

st.subheader("⚙️ スクレイピング設定")

col1, col2, col3 = st.columns(3)

with col1:
    data_scope = st.radio(
        "データ範囲",
        options=["将来レース（スクレイピング）", "過去3年分"],
        help="取得するレースの範囲を選択",
    )

    if data_scope == "将来レース（スクレイピング）":
        days_ahead = st.slider(
            "何日先までのレースを取得するか",
            min_value=1,
            max_value=30,
            value=14,
            help="今日から指定日数先までのレースを取得します",
        )
    else:
        years_back = st.slider(
            "過去何年分を取得するか",
            min_value=1,
            max_value=5,
            value=3,
            help="過去N年分のレースデータを取得します",
        )
        days_ahead = years_back * 365

with col2:
    if data_scope == "将来レース（スクレイピング）":
        end_date = datetime.now() + timedelta(days=days_ahead)
        st.info(f"取得範囲: 今日 ～ {end_date.strftime('%Y年%m月%d日')}")
    else:
        start_date = datetime.now() - timedelta(days=days_ahead)
        st.info(f"取得範囲: {start_date.strftime('%Y年%m月%d日')} ～ 今日")

with col3:
    use_mock = st.checkbox(
        "テストモードを使用",
        value=False,
        help="JRA公式サイトへのアクセスが失敗する場合、モックデータでテストできます",
    )
    if use_mock:
        st.warning("⚠️ テストモード：本番データではなくモックデータを使用します")

st.markdown("---")

# ========================
# スクレイピング実行
# ========================

st.subheader("🔄 スクレイピング実行")

# ボタンラベルをデータ範囲に応じて変更
button_label = (
    "📥 将来レース情報を取得"
    if data_scope == "将来レース（スクレイピング）"
    else "📥 過去3年分のレース情報を取得"
)

if st.button(button_label, type="primary", use_container_width=True):
    with st.status("レース情報を取得中...", expanded=True) as status:
        try:
            if data_scope == "将来レース（スクレイピング）":
                # 将来のレースをスクレイピング
                if use_mock:
                    st.write(f"📊 テストモード：{days_ahead} 日先までのモックレース情報を生成中...")
                else:
                    st.write(f"📊 JRA公式サイトから {days_ahead} 日先までのレース情報を取得中...")

                upcoming_races = fetch_upcoming_races(days_ahead=days_ahead, use_mock=use_mock)
            else:
                # 過去のレースを取得（現在はモックデータを使用）
                st.write(f"📊 過去 {years_back} 年分のレース情報を取得中...")

                # 過去データの場合はモックを使用（実際のスクレイピングは複雑なため）
                upcoming_races = fetch_upcoming_races(
                    days_ahead=days_ahead, use_mock=True  # 過去データは常にモックを使用
                )

            if not upcoming_races:
                st.error("❌ レース情報が取得できませんでした")
                st.info("⚠️ 考えられる原因:")
                st.info("  - JRA公式サイトのHTML構造が変更された可能性")
                st.info("  - ネットワーク接続エラー")
                st.info("  - スクレイピング対象期間にレースがない")
                st.info("💡 詳細はサーバーログを確認してください")
                st.info("💡 テストモードをONにしてモックデータで試してください")
                st.stop()

            st.write(f"✅ {len(upcoming_races)} 件のレース情報を取得しました")

            # レース情報を表示
            st.write("**取得したレース:**")
            races_df_data = []
            for race in upcoming_races[:10]:
                races_df_data.append(
                    {
                        "日付": race.get("race_date"),
                        "レース名": race.get("title"),
                        "レースID": race.get("race_id"),
                        "日数": race.get("days_from_today"),
                    }
                )

            st.dataframe(races_df_data, use_container_width=True, hide_index=True)

            if len(upcoming_races) > 10:
                st.caption(f"他 {len(upcoming_races) - 10} 件のレース")

            # データベースへの自動登録
            st.write("💾 取得したレース情報をデータベースに登録中...")

            try:
                # 出馬表を全レース取得（出馬表がある場合）
                all_race_ids = [r["race_id"] for r in upcoming_races if r.get("race_id")]

                if all_race_ids:
                    # 出馬表取得のためのレース選択（オプション）
                    st.write("**出馬表を取得するレースを選択（任意）:**")

                    selected_races = st.multiselect(
                        "レースを選択",
                        options=[f"{r['race_date']} - {r['title']}" for r in upcoming_races],
                        help="出馬表（出走馬情報）を取得するレースを選択してください。選択しない場合はレース情報のみ登録します。",
                        key="race_selector",
                    )

                    race_cards = []
                    if selected_races:
                        # 選択されたレースのrace_idを取得
                        selected_race_ids = []
                        for selected in selected_races:
                            for race in upcoming_races:
                                if f"{race['race_date']} - {race['title']}" == selected:
                                    selected_race_ids.append(race["race_id"])
                                    break

                        if st.button(
                            "🐴 出馬表を取得して登録", type="secondary", use_container_width=True
                        ):
                            st.write(f"📋 {len(selected_race_ids)} 件のレースの出馬表を取得中...")
                            race_cards = fetch_multiple_race_cards(selected_race_ids)
                            total_entries = sum(len(card.get("entries", [])) for card in race_cards)
                            st.write(f"✅ {total_entries} 頭の出走馬情報を取得しました")

                # レース基本情報をデータベースに登録（常に実施）
                races_for_db = []
                for race in upcoming_races:
                    race_id = race.get("race_id")
                    if race_id:
                        # race_idから情報を抽出
                        year = int(race_id[0:4])
                        month = int(race_id[4:6])
                        day = int(race_id[6:8])
                        race_date = f"{year:04d}-{month:02d}-{day:02d}"

                        races_for_db.append(
                            {
                                "race_date": race_date,
                                "course": "未取得",
                                "race_no": 0,
                                "distance_m": 0,
                                "surface": "未取得",
                                "title": race.get("title", f"レース {race_id}"),
                            }
                        )

                if races_for_db:
                    upsert_race.RaceUpsert().upsert_races(races_for_db)
                    st.write(f"✅ {len(races_for_db)} 件のレース情報を登録しました")

                # 出馬表が取得されている場合は出走情報も登録
                if race_cards:
                    all_entries = []
                    for card in race_cards:
                        race_id = card.get("race_id")
                        entries = card.get("entries", [])

                        for entry in entries:
                            entry["race_id"] = race_id
                            all_entries.append(entry)

                    if all_entries:
                        # 馬情報を登録
                        horses_to_register = []
                        for entry in all_entries:
                            if entry.get("horse_name"):
                                horses_to_register.append(
                                    {
                                        "raw_name": entry["horse_name"],
                                        "sex": "不明",
                                        "birth_year": 2020,
                                    }
                                )

                        if horses_to_register:
                            from etl import upsert_master

                            upsert_master.MasterDataUpsert().upsert_horses(horses_to_register)

                        # 出走情報を登録
                        upsert_entry.EntryUpsert().upsert_entries(all_entries)
                        st.write(f"✅ {len(all_entries)} 件の出走情報を登録しました")

                st.success("✨ データベースへの登録が完了しました")

            except Exception as e:
                st.error(f"❌ データベース登録エラー: {e}")
                logger.error(f"Database registration error: {e}", exc_info=True)

            status.update(label="✅ 完了", state="complete")

        except Exception as e:
            status.update(label="❌ エラー", state="error")
            st.error(f"スクレイピングエラー: {e}")
            logger.error(f"Scraping error: {e}", exc_info=True)

st.markdown("---")

# ========================
# 情報
# ========================

st.info(
    """
    💡 **将来レース情報について**

    このページでは以下の機能を提供しています：

    ### 📊 データ取得モード
    - **将来レース（スクレイピング）**：JRA公式サイトから今後のレース情報を自動取得
    - **過去3年分**：過去のレースデータをデータベースに蓄積
    - どちらを選択してもデータベースに自動的に保存されます

    ### 🐴 出馬表取得（オプション）
    - 選択したレースの出走馬情報を取得可能
    - 馬名、騎手、調教師などの詳細情報を含む
    - 任意で実施（しない場合はレース基本情報のみ登録）

    ### 💾 自動データベース登録
    - 取得したレース情報を自動的にデータベースに登録
    - 登録後は予測分析で即座に使用可能
    - 出馬表データがあれば同時に登録

    ### ⚠️ 注意事項
    - スクレイピングに時間がかかる場合があります
    - JRA公式サイトの構造変更に対応が必要な場合があります
    - robots.txt の規定に従ってリクエストを制限しています
    - 過去データはモックデータを使用しています
    """
)

st.markdown("---")

st.caption("🔄 最終更新: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
