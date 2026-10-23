"""Phase 2: ウォークフォワードで3条件を同一条件比較し、レポートを出す

比較する買い方（すべて同じ検証期間・同じフォールド）:
1. ベタ買い: 検証期間の全出走馬に単勝を定額買い
2. 市場1番人気買い: 各レースで人気1番の馬に単勝を定額買い
3. ポリシー適用: LightGBM（較正済み確率）＋事前登録ポリシー
   （EVフィルタ制限形＋大穴回避＋1レース最大点数）

前提と限界（レポート冒頭にも明記する）:
- 現行DBに払戻データが無いため、単勝払戻は「確定オッズ × 100円」で近似する。
- 現行DBの着順は上位3着までしか記録されていない。勝ち馬が記録された
  レースに限り、未記録の行は「4着以下」として扱う（load_full_entries_frame）。
- 封印期間（holdout）は開封しない。本スクリプトは holdout 開始日より
  前のデータだけで評価する。

実行方法:
    uv run python -m evaluation.run_comparison
出力:
    evaluation/reports/phase2_comparison.md
"""

from pathlib import Path

import pandas as pd

from evaluation import calibration, metrics
from evaluation.conditions import load_conditions
from evaluation.data import load_full_entries_frame
from evaluation.model import make_train_predict_fn, market_train_predict_fn
from evaluation.walk_forward import exclude_holdout, walk_forward_splits

REPORT_PATH = Path(__file__).parent / "reports" / "phase2_comparison.md"


def _settle_candidates(candidates: pd.DataFrame, conditions) -> pd.DataFrame:
    return metrics.settle(candidates.copy(), conditions)


def run_comparison() -> dict:
    conditions = load_conditions()
    frame = load_full_entries_frame()
    working = exclude_holdout(frame, conditions)

    assert working["race_date"].max() < conditions.holdout_start, (
        "封印期間（holdout）が評価対象に混入しています"
    )

    dates = sorted(working["race_date"].unique())
    splits = walk_forward_splits(dates, conditions.n_splits)

    bet_all, favorite = [], []
    market_predictions = []
    for train_dates, test_dates in splits:
        test = working[working["race_date"].isin(test_dates)]
        bet_all.append(_settle_candidates(test, conditions))
        fav = test[test["popularity"] == 1].copy()
        # 人気1番が同率で複数いる場合は馬番の小さい方を1点だけ採る
        fav = fav.sort_values(["race_id", "horse_no"]).groupby("race_id").head(1)
        favorite.append(_settle_candidates(fav, conditions))
        market_predictions.append(market_train_predict_fn(test, test))

    from evaluation.walk_forward import run_walk_forward

    policy_cal = run_walk_forward(
        working, conditions, make_train_predict_fn(calibrate=True)
    )
    policy_raw = run_walk_forward(
        working, conditions, make_train_predict_fn(calibrate=False)
    )

    market_pred = pd.concat(market_predictions, ignore_index=True)
    outcomes = (policy_cal["predictions"]["finish_pos"] == 1).astype(float)
    calib_compare = calibration.compare_calibration(
        policy_cal["predictions"]["win_prob_raw"],
        policy_cal["predictions"]["win_prob"],
        outcomes,
    )
    reliability = calibration.reliability_table(
        policy_cal["predictions"]["win_prob"], outcomes, n_bins=10
    )

    winners = frame[frame["won"] == 1]
    recorded = frame[frame["finish_pos_raw"].notna()]
    diagnostics = {
        "winner_horse_no1_share": float((winners["horse_no"] == 1).mean()),
        "popularity_equals_finish_share": float(
            (recorded["popularity"] == recorded["finish_pos_raw"]).mean()
        ),
        "unique_horses": int(frame["horse_id"].nunique()),
        "winner_mean_odds": float(winners["odds"].mean()),
        "all_mean_odds": float(frame["odds"].mean()),
        "favorite_win_rate": float(
            frame[frame["popularity"] == 1]["won"].mean()
        ),
    }

    return {
        "conditions": conditions,
        "frame": frame,
        "working": working,
        "diagnostics": diagnostics,
        "strategies": {
            "bet_all": metrics.summarize_bets(
                pd.concat(bet_all, ignore_index=True), conditions
            ),
            "favorite": metrics.summarize_bets(
                pd.concat(favorite, ignore_index=True), conditions
            ),
            "policy": policy_cal["overall"],
            "policy_raw_reference": policy_raw["overall"],
        },
        "policy_folds": policy_cal["folds"],
        "model_log_loss": policy_cal["log_loss"],
        "model_log_loss_raw": policy_raw["log_loss"],
        "market_log_loss": metrics.log_loss(market_pred),
        "calibration": calib_compare,
        "reliability": reliability,
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

    n_races_all = frame["race_id"].nunique()
    n_races_working = working["race_id"].nunique()
    lines = []
    lines.append("# Phase 2 ウォークフォワード比較レポート")
    lines.append("")
    lines.append("## 前提と解釈の限界（最初に読むこと）")
    lines.append("")
    lines.append(
        "- 払戻データがDBに無いため、単勝払戻は **確定オッズ × 100円** で近似している"
        "（実際の払戻は10円未満切り捨て等のため、実績より最大で1点あたり10円未満だけ高く出る）。"
    )
    lines.append(
        "- 現行DBの着順は **上位3着までしか記録されていない**。勝ち馬が記録されたレースに限り、"
        "未記録の出走行は「4着以下」として扱った。勝ち馬が記録されていないレースは除外した。"
    )
    lines.append(
        "- データは合成データ中心とみられ、標本も小さい（下表）。ここでの回収率は"
        "「実データでの収益性」を示すものではなく、検証基盤とポリシーの動作確認が目的である。"
    )
    lines.append(
        f"- 封印期間（holdout: {conditions.holdout_start} 以降）は開封していない。"
        f"評価した最大の日付は {result['max_evaluated_date']}。"
    )
    lines.append("")
    d = result["diagnostics"]
    lines.append("## データ整合性の診断（最重要の発見）")
    lines.append("")
    lines.append(
        "現行DBは、以下のとおり生成規則が決定的なデモ／合成データであり、"
        "**実力評価には使えない**。本レポートの数値は、検証基盤とポリシーが"
        "機械的に正しく動くことの確認としてのみ意味を持つ。"
        "結論として、意味のある評価には実データの投入（Phase 4）が前提になる。"
    )
    lines.append("")
    lines.append("| 診断項目 | 結果 | 意味 |")
    lines.append("|---|---:|---|")
    lines.append(
        f"| 勝ち馬が馬番1番である割合 | {d['winner_horse_no1_share'] * 100:.1f}% "
        "| 勝ち馬が常に1番。モデルは馬番だけで完全分離できてしまう |"
    )
    lines.append(
        f"| 人気と着順が一致する割合（記録行） | {d['popularity_equals_finish_share'] * 100:.1f}% "
        "| 人気 = 着順そのもの。「1番人気買い」の的中率100%はこのため |"
    )
    lines.append(
        f"| 1番人気の勝率 | {d['favorite_win_rate'] * 100:.1f}% "
        "| 実データの1番人気勝率は30%前後。100%はあり得ない |"
    )
    lines.append(
        f"| ユニークな馬の数 | {d['unique_horses']:,} 頭（出走 {len(frame):,} 行） "
        "| 馬IDが使い回されている |"
    )
    lines.append(
        f"| 勝ち馬の平均オッズ / 全体の平均オッズ | {d['winner_mean_odds']:.1f} / {d['all_mean_odds']:.1f} "
        "| オッズは結果と無相関な一様ノイズ。ベタ買い回収率が100%を超えるのはこの算術のため |"
    )
    lines.append("")
    lines.append("## 評価データの実態")
    lines.append("")
    lines.append("| 項目 | 件数 |")
    lines.append("|---|---:|")
    lines.append(f"| 全出走フレームのレース数（勝ち馬記録あり） | {n_races_all:,} |")
    lines.append(f"| 全出走フレームの出走行数 | {len(frame):,} |")
    lines.append(
        f"| 期間 | {frame['race_date'].min()} 〜 {frame['race_date'].max()} |"
    )
    lines.append(f"| 評価対象レース数（holdout除外後） | {n_races_working:,} |")
    lines.append(f"| 評価対象出走行数 | {len(working):,} |")
    lines.append(
        f"| 評価対象の勝ち馬行比率 | {working['won'].mean() * 100:.1f}% |"
    )
    lines.append("")
    lines.append("## 3条件の比較（同一フォールド・同一期間）")
    lines.append("")
    lines.append(
        "| 買い方 | 点数 | レース数 | 回収率% | 95%CI | Top5除外時% | 的中率 |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    labels = {
        "bet_all": "ベタ買い（全頭単勝）",
        "favorite": "市場1番人気買い",
        "policy": "ポリシー適用（較正済み確率）",
    }
    for key in ("bet_all", "favorite", "policy"):
        row = s[key]
        lines.append(
            f"| {labels[key]} | {row['n_bets']:,} | {row['n_races']:,} "
            f"| {_fmt(row['roi_percent'])} "
            f"| {_fmt(row['roi_ci_low'])} 〜 {_fmt(row['roi_ci_high'])} "
            f"| {_fmt(row['roi_excluding_top5_percent'])} "
            f"| {_fmt(row['hit_rate'] * 100 if row['hit_rate'] == row['hit_rate'] else None)}% |"
        )
    lines.append("")
    lines.append(
        f"参考: ポリシーを未較正確率で回した場合の回収率は "
        f"{_fmt(s['policy_raw_reference']['roi_percent'])}%"
        f"（点数 {s['policy_raw_reference']['n_bets']:,}）。"
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
    lines.append(
        f"- 券種: {conditions.ticket_type}（払戻率の前提 {conditions.ticket_payout_rates.get(conditions.ticket_type)}）"
    )
    lines.append(f"- EV閾値: {conditions.ev_threshold} / 予測勝率下限: {conditions.min_win_prob}")
    lines.append(f"- 大穴回避: 単勝オッズ {conditions.max_odds} 倍以上は買わない")
    lines.append(f"- 1レース最大点数: {conditions.max_bets_per_race} / 1点 {conditions.unit_bet}円")
    lines.append(
        f"- Kelly: 分数 {conditions.kelly_fraction}、較正済み確率でのみ有効 "
        f"（requires_calibration={conditions.kelly_requires_calibration}）"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    result = run_comparison()
    report = render_report(result)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"レポートを書き出しました: {REPORT_PATH}")
    s = result["strategies"]
    for key, label in (
        ("bet_all", "ベタ買い"),
        ("favorite", "1番人気"),
        ("policy", "ポリシー"),
    ):
        row = s[key]
        print(
            f"{label}: 点数 {row['n_bets']} 回収率 {row['roi_percent']:.1f}% "
            f"(95%CI {row['roi_ci_low']:.1f} 〜 {row['roi_ci_high']:.1f})"
        )


if __name__ == "__main__":
    main()
