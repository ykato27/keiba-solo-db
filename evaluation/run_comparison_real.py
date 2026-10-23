"""Phase 4 前倒し: 実データ（JRAEN 取得）でのウォークフォワード比較

scripts/fetch_jraen_results.py で data/keiba_real.db に取り込んだ
JRA公式結果を使い、Phase 2 と同じ3条件（ベタ買い／1番人気／ポリシー）を
同一条件で比較する。精算には払戻テーブル（payouts）の実払戻を使う。

事前登録条件（evaluation/betting_conditions.yaml）のポリシー値は
そのまま使い、holdout 開始日だけを実データの期間に合わせて差し替える
（取得した最終月を封印期間として評価から外す）。

前提と限界はレポート冒頭に明記する。要点:
- 取得範囲は限定的（数ヶ月・一部の開催日）で、標本は小さい。
- 馬体重は JRAEN の結果ページに無いため特徴量から欠落する
  （horse_weight は NULL → 特徴量側で 0 埋め）。
- 前走間隔（days_since_last_race）は取得範囲内でのみ計算されるため、
  期間の序盤では過小になる。

実行方法:
    uv run python -m evaluation.run_comparison_real
出力:
    evaluation/reports/phase2_comparison_real.md
"""

import dataclasses
import sqlite3
from collections import Counter
from pathlib import Path

import pandas as pd

from evaluation import calibration, metrics
from evaluation.conditions import load_conditions
from evaluation.data import load_full_entries_frame
from evaluation.model import make_train_predict_fn, market_train_predict_fn
from evaluation.policy import select_policy_bets
from evaluation.walk_forward import exclude_holdout, run_walk_forward, walk_forward_splits

REAL_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "keiba_real.db"
REPORT_PATH = Path(__file__).parent / "reports" / "phase2_comparison_real.md"
# 取得した最終月（2025-06）を封印期間として評価から外す
REAL_HOLDOUT_START = "2025-06-01"


def load_win_payouts(db_path: Path = REAL_DB_PATH) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT race_id, payout_yen FROM payouts WHERE bet_type = 'win'"
        ).fetchall()
    finally:
        conn.close()
    return {int(race_id): int(payout) for race_id, payout in rows}


def settle_real(bets: pd.DataFrame, win_payouts: dict, unit_bet: int) -> pd.DataFrame:
    """実払戻で精算する（metrics.settle の実データ版）

    的中した単勝の払戻は payouts テーブルの実額（100円あたり）を使う。
    払戻が無いレースの的中は 0 として扱い、件数は呼び出し側で報告する。
    """
    settled = bets.copy()
    settled["stake"] = float(unit_bet)
    payout = settled["race_id"].map(win_payouts)
    settled["return_amount"] = 0.0
    won = settled["finish_pos"] == 1
    settled.loc[won, "return_amount"] = payout[won].fillna(0.0)
    settled["missing_payout"] = won & payout.isna()
    return settled


def verify_payout_vs_odds(frame: pd.DataFrame, win_payouts: dict) -> dict:
    """単勝払戻と「確定オッズ×100」の一致を検証する（データ整合性）"""
    winners = frame[frame["finish_pos"] == 1]
    diffs = []
    missing = 0
    for row in winners.itertuples():
        payout = win_payouts.get(int(row.race_id))
        if payout is None:
            missing += 1
            continue
        diffs.append(abs(payout - row.odds * 100))
    return {
        "winner_rows": len(winners),
        "missing_payouts": missing,
        "max_diff_yen": max(diffs) if diffs else None,
        "mean_diff_yen": (sum(diffs) / len(diffs)) if diffs else None,
    }


def run_comparison_real() -> dict:
    conditions = dataclasses.replace(
        load_conditions(), holdout_start=REAL_HOLDOUT_START
    )
    frame = load_full_entries_frame(db_path=REAL_DB_PATH)
    win_payouts = load_win_payouts()
    payout_check = verify_payout_vs_odds(frame, win_payouts)
    working = exclude_holdout(frame, conditions)
    assert working["race_date"].max() < conditions.holdout_start

    dates = sorted(working["race_date"].unique())
    splits = walk_forward_splits(dates, conditions.n_splits)

    bet_all, favorite, missing_counts = [], [], Counter()
    market_predictions = []
    for _, test_dates in splits:
        test = working[working["race_date"].isin(test_dates)]
        for name, candidates in (
            ("bet_all", test),
            (
                "favorite",
                test[test["popularity"] == 1]
                .sort_values(["race_id", "horse_no"])
                .groupby("race_id")
                .head(1),
            ),
        ):
            settled = settle_real(candidates, win_payouts, conditions.unit_bet)
            missing_counts[name] += int(settled["missing_payout"].sum())
            (bet_all if name == "bet_all" else favorite).append(settled)
        market_predictions.append(market_train_predict_fn(test, test))

    policy_run = run_walk_forward(
        working, conditions, make_train_predict_fn(calibrate=True)
    )
    policy_raw_run = run_walk_forward(
        working, conditions, make_train_predict_fn(calibrate=False)
    )
    policy_bets = settle_real(
        select_policy_bets(policy_run["predictions"], conditions),
        win_payouts,
        conditions.unit_bet,
    )
    missing_counts["policy"] += int(policy_bets["missing_payout"].sum())

    market_pred = pd.concat(market_predictions, ignore_index=True)
    outcomes = (policy_run["predictions"]["finish_pos"] == 1).astype(float)
    calib_compare = calibration.compare_calibration(
        policy_run["predictions"]["win_prob_raw"],
        policy_run["predictions"]["win_prob"],
        outcomes,
    )
    reliability = calibration.reliability_table(
        policy_run["predictions"]["win_prob"], outcomes, n_bins=10
    )

    winners = working[working["finish_pos"] == 1]
    diagnostics = {
        "winner_horse_no1_share": float((winners["horse_no"] == 1).mean()),
        "favorite_win_rate": float(working[working["popularity"] == 1]["won"].mean()),
        "winner_mean_odds": float(winners["odds"].mean()),
        "all_mean_odds": float(working["odds"].mean()),
        "unique_horses": int(working["horse_id"].nunique()),
    }

    return {
        "conditions": conditions,
        "frame": frame,
        "working": working,
        "payout_check": payout_check,
        "missing_payout_bets": dict(missing_counts),
        "strategies": {
            "bet_all": metrics.summarize_bets(
                pd.concat(bet_all, ignore_index=True), conditions
            ),
            "favorite": metrics.summarize_bets(
                pd.concat(favorite, ignore_index=True), conditions
            ),
            "policy": metrics.summarize_bets(policy_bets, conditions),
        },
        "policy_folds": policy_run["folds"],
        "model_log_loss": policy_run["log_loss"],
        "model_log_loss_raw": policy_raw_run["log_loss"],
        "market_log_loss": metrics.log_loss(market_pred),
        "calibration": calib_compare,
        "reliability": reliability,
        "diagnostics": diagnostics,
        "max_evaluated_date": str(working["race_date"].max()),
    }


def _fmt(value, digits=1):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return f"{value:,.{digits}f}"


def render_report(result: dict) -> str:
    conditions = result["conditions"]
    frame = result["frame"]
    working = result["working"]
    s = result["strategies"]
    pc = result["payout_check"]
    d = result["diagnostics"]

    lines = []
    lines.append("# Phase 4（前倒し）実データ ウォークフォワード比較レポート")
    lines.append("")
    lines.append("## データの出所と前提")
    lines.append("")
    lines.append(
        "- 出所: JRA公式英語データサービス（https://jra.jp/JRAEN/AP/common/main、"
        "JRA Race Card & Results）。取得方法と規約上の注意は docs/REAL_DATA.md を参照。"
    )
    lines.append(
        "- 精算は払戻テーブル（payouts）の **実払戻** で行った。"
        f"単勝払戻と「確定オッズ×100」の差は最大 {_fmt(pc['max_diff_yen'], 0)} 円"
        f"（平均 {_fmt(pc['mean_diff_yen'], 2)} 円、勝ち馬 {pc['winner_rows']:,} 件中"
        f"払戻なし {pc['missing_payouts']} 件）。"
    )
    lines.append(
        "- 馬体重は JRAEN の結果ページに掲載が無いため特徴量に含まれない。"
        "前走間隔は取得範囲内でのみ計算され、期間序盤では過小になる。"
    )
    lines.append(
        f"- 封印期間（holdout: {conditions.holdout_start} 以降）は評価から外した。"
        f"評価した最大の日付は {result['max_evaluated_date']}。"
    )
    lines.append(
        "- 標本はまだ小さい（下表）。本格評価には、最低でも数十開催日・"
        "数千レース規模（検証フォールドあたり数百レース）が必要で、"
        "現状の CI の広さがその不足をそのまま表している。"
    )
    lines.append("")
    lines.append("## データの実態と整合性")
    lines.append("")
    lines.append("| 項目 | 件数 |")
    lines.append("|---|---:|")
    lines.append(f"| 取り込みレース数（全期間） | {frame['race_id'].nunique():,} |")
    lines.append(f"| 取り込み出走行数 | {len(frame):,} |")
    lines.append(f"| 期間 | {frame['race_date'].min()} 〜 {frame['race_date'].max()} |")
    lines.append(f"| 評価対象レース数（holdout除外後） | {working['race_id'].nunique():,} |")
    lines.append(f"| 評価対象出走行数 | {len(working):,} |")
    lines.append(
        f"| 払戻が無く精算できなかった的中 | {result['missing_payout_bets']} |"
    )
    lines.append("")
    lines.append("| 整合性チェック（合成データとの対比） | 結果 |")
    lines.append("|---|---:|")
    lines.append(f"| 勝ち馬が馬番1番である割合 | {d['winner_horse_no1_share'] * 100:.1f}% |")
    lines.append(f"| 1番人気の勝率 | {d['favorite_win_rate'] * 100:.1f}% |")
    lines.append(f"| 勝ち馬の平均オッズ / 全体の平均オッズ | {d['winner_mean_odds']:.1f} / {d['all_mean_odds']:.1f} |")
    lines.append(f"| ユニークな馬の数（評価期間） | {d['unique_horses']:,} 頭 |")
    lines.append("")
    lines.append("## 3条件の比較（同一フォールド・同一期間、実払戻で精算）")
    lines.append("")
    lines.append("| 買い方 | 点数 | レース数 | 回収率% | 95%CI | Top5除外時% | 的中率 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    labels = {
        "bet_all": "ベタ買い（全頭単勝）",
        "favorite": "市場1番人気買い",
        "policy": "ポリシー適用（較正済み確率）",
    }
    for key in ("bet_all", "favorite", "policy"):
        row = s[key]
        hit = row["hit_rate"] * 100 if row["hit_rate"] == row["hit_rate"] else None
        lines.append(
            f"| {labels[key]} | {row['n_bets']:,} | {row['n_races']:,} "
            f"| {_fmt(row['roi_percent'])} "
            f"| {_fmt(row['roi_ci_low'])} 〜 {_fmt(row['roi_ci_high'])} "
            f"| {_fmt(row['roi_excluding_top5_percent'])} "
            f"| {_fmt(hit)}% |"
        )
    lines.append("")
    lines.append("## 予測精度とキャリブレーション")
    lines.append("")
    lines.append("| 指標 | 値 |")
    lines.append("|---|---:|")
    lines.append(f"| モデル LogLoss（較正済み） | {_fmt(result['model_log_loss'], 4)} |")
    lines.append(f"| モデル LogLoss（未較正） | {_fmt(result['model_log_loss_raw'], 4)} |")
    lines.append(f"| 市場（オッズ暗黙確率）LogLoss | {_fmt(result['market_log_loss'], 4)} |")
    c = result["calibration"]
    lines.append(f"| LogLoss 較正前→後 | {_fmt(c['log_loss_raw'], 4)} → {_fmt(c['log_loss_calibrated'], 4)} |")
    lines.append(f"| Brier 較正前→後 | {_fmt(c['brier_raw'], 4)} → {_fmt(c['brier_calibrated'], 4)} |")
    lines.append("")
    lines.append("### 信頼性テーブル（較正済み確率、検証期間の合算）")
    lines.append("")
    lines.append("| 予測確率帯 | 件数 | 平均予測 | 実績勝率 |")
    lines.append("|---|---:|---:|---:|")
    for row in result["reliability"].itertuples():
        lines.append(
            f"| {row.bin} | {int(row.n):,} | {_fmt(row.mean_pred, 3)} | {_fmt(row.win_rate, 3)} |"
        )
    lines.append("")
    lines.append("## ポリシーのフォールド別内訳")
    lines.append("")
    lines.append("（回収率は run_walk_forward 内部のオッズ近似ベース。総合値は上の実払戻ベースを正とする）")
    lines.append("")
    lines.append("| Fold | 学習期間 | 検証期間 | 点数 | 回収率% | LogLoss |")
    lines.append("|---:|---|---|---:|---:|---:|")
    for fold in result["policy_folds"]:
        lines.append(
            f"| {fold['fold']} | {fold['train_period'][0]} 〜 {fold['train_period'][1]} "
            f"| {fold['test_period'][0]} 〜 {fold['test_period'][1]} "
            f"| {fold['n_bets']:,} | {_fmt(fold['roi_percent'])} | {_fmt(fold['log_loss'], 4)} |"
        )
    lines.append("")
    lines.append("## 事前登録した買い条件（この評価で使った値）")
    lines.append("")
    lines.append(f"- 券種: {conditions.ticket_type} / EV閾値: {conditions.ev_threshold} / 予測勝率下限: {conditions.min_win_prob}")
    lines.append(f"- 大穴回避: 単勝オッズ {conditions.max_odds} 倍以上は買わない / 1レース最大点数: {conditions.max_bets_per_race} / 1点 {conditions.unit_bet}円")
    lines.append(f"- Kelly: 分数 {conditions.kelly_fraction}、較正済み確率でのみ有効")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    try:
        result = run_comparison_real()
    except ValueError as e:
        print(f"評価を実行できません: {e}")
        print(
            "実データの開催日数が不足しています"
            "（scripts/fetch_jraen_results.py で取得を再開してください）。"
        )
        raise SystemExit(1)
    report = render_report(result)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"レポートを書き出しました: {REPORT_PATH}")
    for key, label in (("bet_all", "ベタ買い"), ("favorite", "1番人気"), ("policy", "ポリシー")):
        row = result["strategies"][key]
        print(
            f"{label}: 点数 {row['n_bets']} 回収率 {row['roi_percent']:.1f}% "
            f"(95%CI {row['roi_ci_low']:.1f} 〜 {row['roi_ci_high']:.1f})"
        )


if __name__ == "__main__":
    main()
