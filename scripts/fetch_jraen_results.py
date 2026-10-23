"""JRA公式英語サービス（JRAEN）から実データを取得し、実データ用DBへ取り込む

使い方:
    uv run python scripts/fetch_jraen_results.py \
        --dates 20250112,20250119,20250209 \
        [--interval 6.0] [--db-path data/keiba_real.db]

方針:
- 取得元は JRA公式の英語データサービス https://jra.jp/JRAEN のみ
  （www.jra.go.jp は本環境で 403、netkeiba は規約上のリスクのため不使用）。
- リクエスト間隔は既定6秒（10件/分）。403/429 が返ったら即中止する。
- 1レースごとにコミットするので、中断しても再実行で続きから進める
  （取り込み済みレースはスキップ）。
- 本番DB（data/keiba.db）には触れない。保存先は data/keiba_real.db。
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import db as app_db  # noqa: E402
from scraper import jraen, jraen_import  # noqa: E402

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "keiba_real.db"
SOURCE_DESCRIPTION = (
    "JRA公式英語データサービス (https://jra.jp/JRAEN/AP/common/main)"
    " — JRA Race Card & Results。日本中央競馬会が公式に公開する"
    "レース結果（全着順・確定オッズ・人気・払戻）を取得。"
)


def _fetch_and_parse(client, ref, stats, max_attempts: int = 3):
    """1レース分の取得＋パース（FetchError は間隔を空けて再試行）

    サーバーが一時的にエラーページを返すことがあるため、レース単位で
    最大 max_attempts 回まで試し、最終的に失敗したら None を返して
    呼び出し側がそのレースだけをスキップする。FetchBlocked は
    そのまま送出して取得全体を中止させる。
    """
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            html = client.fetch_race_result_html(ref)
            return jraen.parse_running_html(html, ref)
        except jraen.FetchError as e:
            last_error = e
            stats["fetch_retries"] += 1
            print(f"  [retry {attempt}/{max_attempts}] {ref}: {e}", flush=True)
            if attempt < max_attempts:
                time.sleep(10 * attempt)
    print(f"  [failed] {ref}: {last_error}", flush=True)
    stats["races_failed"] += 1
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="JRAEN から実データを取得する")
    parser.add_argument("--dates", required=True, help="開催日 YYYYMMDD をカンマ区切りで")
    parser.add_argument("--interval", type=float, default=6.0, help="リクエスト間隔（秒）")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--max-races-per-date", type=int, default=None)
    parser.add_argument(
        "--offset", type=int, default=0,
        help="開催日のレース一覧の何件目から取得するか（分割実行用）",
    )
    args = parser.parse_args(argv)

    dates = [d.strip() for d in args.dates.split(",") if d.strip()]
    args.db_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not args.db_path.exists()

    conn = app_db.get_connection(db_path=args.db_path)
    jraen_import.ensure_real_schema(conn)
    # WAL だと本体ファイルへの反映が遅延し、長時間プロセスの成果物が
    # 失われやすい環境があるため、実データDBは DELETE ジャーナルにする
    # （コミットごとに本体ファイルへ同期的に書かれる）。
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.commit()
    dims = jraen_import.DimensionCache(conn)

    existing = {
        row[0] for row in conn.execute("SELECT race_id FROM races").fetchall()
    }
    print(f"DB: {args.db_path}（新規={is_new}、既存レース {len(existing)} 件）", flush=True)

    client = jraen.JraenClient(min_interval=args.interval)
    stats = Counter()
    payoff_violations = []

    try:
        known_dates = client.fetch_meeting_dates(int(dates[0][:4]))
        for date in dates:
            if date not in known_dates:
                print(f"[skip] {date}: 開催日ではありません", flush=True)
                stats["dates_not_meetings"] += 1
                continue
            refs = client.fetch_race_refs(date)
            if args.offset:
                refs = refs[args.offset:]
            if args.max_races_per_date:
                refs = refs[: args.max_races_per_date]
            print(f"== {date}: {len(refs)} レース", flush=True)
            for ref in refs:
                race_id = jraen_import.race_id_for(ref)
                if race_id in existing:
                    stats["races_skipped_existing"] += 1
                    continue
                parsed = _fetch_and_parse(client, ref, stats)
                if parsed is None:
                    continue
                jraen_import.import_race(conn, parsed, ref, dims)
                existing.add(race_id)
                stats["races_imported"] += 1
                stats["entries_imported"] += len(parsed["entries"])
                stats["skipped_result_rows"] += parsed["skipped_result_rows"]
                for p in parsed["payoffs"]:
                    stats[f"payoffs_{p['bet_type']}"] += 1
                # 払戻の整合性チェック（単勝の組合せ=勝ち馬、複勝は3着以内）
                winner = next(
                    (e for e in parsed["entries"] if e["finish_pos"] == 1), None
                )
                top3 = {
                    str(e["horse_no"])
                    for e in parsed["entries"]
                    if e["finish_pos"] in (1, 2, 3)
                }
                for p in parsed["payoffs"]:
                    if p["bet_type"] == "win" and winner is not None:
                        if p["combination"] != str(winner["horse_no"]):
                            payoff_violations.append(
                                f"race {race_id}: win payoff {p['combination']}"
                                f" != winner {winner['horse_no']}"
                            )
                    if p["bet_type"] == "place":
                        if p["combination"] not in top3:
                            payoff_violations.append(
                                f"race {race_id}: place payoff {p['combination']}"
                                f" not in top3 {sorted(top3)}"
                            )
                print(
                    f"  [ok] {parsed['course']} {ref['race_no']}R"
                    f" 出走 {len(parsed['entries'])} 払戻 {len(parsed['payoffs'])}",
                    flush=True,
                )
    except jraen.FetchBlocked as e:
        print(f"中止: {e}", flush=True)
        stats["blocked"] += 1
        _write_meta(args.db_path, dates, stats, payoff_violations)
        conn.close()
        return 2
    except jraen.FetchError as e:
        print(f"中止（取得エラー）: {e}", flush=True)
        _write_meta(args.db_path, dates, stats, payoff_violations)
        conn.close()
        return 1

    updated = jraen_import.recompute_days_since_last_race(conn)
    stats["days_since_last_filled"] = updated
    jraen_import.set_meta(conn, "source", SOURCE_DESCRIPTION)
    jraen_import.set_meta(conn, "source_base_url", jraen.BASE_URL)
    _write_meta(args.db_path, dates, stats, payoff_violations)

    totals = conn.execute(
        "SELECT (SELECT COUNT(*) FROM races), (SELECT COUNT(*) FROM race_entries),"
        " (SELECT COUNT(*) FROM payouts),"
        " (SELECT MIN(race_date) FROM races), (SELECT MAX(race_date) FROM races)"
    ).fetchone()
    conn.close()

    print("=" * 60, flush=True)
    print(f"取り込み完了: レース {totals[0]} 件 / 出走 {totals[1]} 件 / 払戻 {totals[2]} 件", flush=True)
    print(f"期間: {totals[3]} 〜 {totals[4]}", flush=True)
    print(f"内訳: {dict(stats)}", flush=True)
    print(f"払戻の整合性違反: {len(payoff_violations)} 件", flush=True)
    for violation in payoff_violations[:10]:
        print(f"  - {violation}", flush=True)
    return 0


def _write_meta(db_path: Path, dates, stats, payoff_violations) -> None:
    meta = {
        "source": SOURCE_DESCRIPTION,
        "source_base_url": jraen.BASE_URL,
        "requested_dates": dates,
        "stats": {k: int(v) for k, v in stats.items()},
        "payoff_violations": payoff_violations,
    }
    meta_path = db_path.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"メタ情報を書き出しました: {meta_path}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
