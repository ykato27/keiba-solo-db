"""
Streamlitでのグラフ表示ヘルパー
Plotlyを使用
"""

import plotly.graph_objects as go
import plotly.express as px
from typing import List, Dict, Any
import pandas as pd
import json
from datetime import datetime


def create_race_entries_table(entries: List[Dict[str, Any]]) -> pd.DataFrame:
    """レース出走馬のテーブルを作成"""
    df_data = []

    for entry in entries:
        df_data.append({
            "馬番": entry.get("horse_no"),
            "馬名": entry.get("horse_name"),
            "騎手": entry.get("jockey_name"),
            "調教師": entry.get("trainer_name"),
            "年齢": entry.get("age"),
            "斤量": entry.get("weight_carried"),
            "勝率": f"{entry.get('win_rate', 0) * 100:.1f}%",
            "連対率": f"{entry.get('place_rate', 0) * 100:.1f}%",
            "複勝率": f"{entry.get('show_rate', 0) * 100:.1f}%",
            "近走指数": f"{entry.get('recent_score', 0):.1f}",
            "人気": entry.get("popularity"),
            "オッズ": f"{entry.get('odds', 0):.1f}",
        })

    return pd.DataFrame(df_data)


def create_horse_metrics_display(horse_details: Dict[str, Any]) -> Dict[str, Any]:
    """馬の指標表示用データを作成"""
    return {
        "馬名": horse_details.get("raw_name"),
        "性別": horse_details.get("sex"),
        "生年": horse_details.get("birth_year"),
        "出走数": int(horse_details.get("races_count", 0)),
        "勝率": f"{horse_details.get('win_rate', 0) * 100:.2f}%",
        "連対率": f"{horse_details.get('place_rate', 0) * 100:.2f}%",
        "複勝率": f"{horse_details.get('show_rate', 0) * 100:.2f}%",
        "近走指数": f"{horse_details.get('recent_score', 0):.2f}",
    }


def create_horse_history_table(history: List[Dict[str, Any]]) -> pd.DataFrame:
    """馬の過去成績テーブルを作成"""
    df_data = []

    for race in history:
        df_data.append({
            "日付": race.get("race_date"),
            "開催地": race.get("course"),
            "R": race.get("race_no"),
            "レース名": race.get("title"),
            "距離": f"{race.get('distance_m')}m",
            "馬場": race.get("surface"),
            "状態": race.get("going"),
            "クラス": race.get("grade"),
            "着順": race.get("finish_pos") if race.get("finish_pos") else "-",
            "枠番": race.get("frame_no"),
            "馬番": race.get("horse_no"),
            "年齢": race.get("age"),
            "斤量": race.get("weight_carried"),
            "時間": f"{race.get('finish_time_seconds'):.1f}秒" if race.get("finish_time_seconds") else "-",
            "着差": race.get("margin") if race.get("margin") else "-",
            "騎手": race.get("jockey_name"),
            "調教師": race.get("trainer_name"),
        })

    df = pd.DataFrame(df_data)
    return df.sort_values("日付", ascending=False)


def create_recent_score_chart(history: List[Dict[str, Any]]) -> go.Figure:
    """近走指数の推移グラフを作成"""
    # 指数の定義：着順と人気から算出
    data = []

    for i, race in enumerate(reversed(history[-10:])):  # 最大10走
        finish_pos = race.get("finish_pos")
        popularity = race.get("popularity")

        if finish_pos is None:
            score = 0
        else:
            # 簡易的な指数：着順が小さいほど高い
            if finish_pos == 1:
                score = 5
            elif finish_pos == 2:
                score = 3
            elif finish_pos == 3:
                score = 2
            else:
                score = 0

            # 人気による調整
            if popularity:
                score *= (1.0 - min(popularity / 10, 0.5))

        data.append({
            "race_index": i,
            "score": score,
            "finish_pos": finish_pos if finish_pos else "出走なし",
            "date": race.get("race_date"),
        })

    df = pd.DataFrame(data)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df["race_index"],
        y=df["score"],
        mode="lines+markers",
        name="近走指数",
        line=dict(color="rgba(0, 100, 200, 0.8)", width=2),
        marker=dict(size=8),
        hovertemplate="<b>%{customdata[0]}</b><br>着順: %{customdata[1]}<br>指数: %{y:.1f}<extra></extra>",
        customdata=df[["date", "finish_pos"]].values,
    ))

    fig.update_layout(
        title="近走指数の推移",
        xaxis_title="過去走（新→古）",
        yaxis_title="指数",
        hovermode="x unified",
        template="plotly_white",
    )

    return fig


def create_distance_preference_chart(distance_pref: str) -> go.Figure:
    """距離別成績グラフを作成"""
    try:
        pref = json.loads(distance_pref)
    except (json.JSONDecodeError, TypeError):
        pref = {}

    if not pref:
        fig = go.Figure()
        fig.add_annotation(text="データなし", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False)
        return fig

    distances = []
    races = []
    wins = []

    for distance, stats in sorted(pref.items(), key=lambda x: int(x[0].rstrip('m'))):
        distances.append(distance)
        races.append(stats.get("races", 0))
        wins.append(stats.get("wins", 0))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=distances,
        y=races,
        name="出走数",
        marker_color="rgba(100, 150, 250, 0.7)",
    ))

    fig.add_trace(go.Bar(
        x=distances,
        y=wins,
        name="勝利数",
        marker_color="rgba(250, 100, 100, 0.7)",
    ))

    fig.update_layout(
        title="距離別成績",
        xaxis_title="距離",
        yaxis_title="レース数",
        barmode="group",
        template="plotly_white",
        hovermode="x unified",
    )

    return fig


def create_surface_preference_chart(surface_pref: str) -> go.Figure:
    """馬場別成績グラフを作成"""
    try:
        pref = json.loads(surface_pref)
    except (json.JSONDecodeError, TypeError):
        pref = {}

    if not pref:
        fig = go.Figure()
        fig.add_annotation(text="データなし", xref="paper", yref="paper",
                          x=0.5, y=0.5, showarrow=False)
        return fig

    surfaces = []
    races = []
    wins = []

    for surface, stats in pref.items():
        surfaces.append(surface)
        races.append(stats.get("races", 0))
        wins.append(stats.get("wins", 0))

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=surfaces,
        y=races,
        name="出走数",
        marker_color="rgba(100, 200, 150, 0.7)",
    ))

    fig.add_trace(go.Bar(
        x=surfaces,
        y=wins,
        name="勝利数",
        marker_color="rgba(250, 150, 100, 0.7)",
    ))

    fig.update_layout(
        title="馬場別成績",
        xaxis_title="馬場",
        yaxis_title="レース数",
        barmode="group",
        template="plotly_white",
        hovermode="x unified",
    )

    return fig
