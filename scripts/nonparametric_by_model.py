"""The non-parametric tests of scripts/nonparametric_tests.py for ONE asset, once for every sentiment model of the dashboard (VADER+FinBERT, VADER, FinBERT):
does the relation between the Reddit sentiment and the price return depend on the model that scores the texts?

The Sentiment Score of the hour is that of EVERY text of the market (the panel Global) of the six communities, posts and comments, scored by the model; it is rebuilt from
the hourly sums of the database exactly like the dashboard does (`dashboard.data.global_hourly` + `sentiment_frame`), because the table `panels` keeps only the combined
model.  As a check, the combined model rebuilt here is compared with the panel Global of the table `panels` (same rows, same Spearman rho).
For each model and target (Current Return = log_return, future return 1h / 2h / 3h / 6h / 12h): Spearman's rho with a 95% block-bootstrap interval (UTC days),
the circular-shift p-value and the usual p-value of the formula, Mann-Whitney U (positive against negative hours) and Kruskal-Wallis (positive / negative / neutral).
Read-only: nothing is written to the database.

Usage:  python scripts/nonparametric_by_model.py [--ticker ES=F | --all] [--db output/reddit.sqlite3] [--boot 1000] [--shifts 2000]
Output: output/reports/nonparametric_by_model_<ticker>.md and .csv, or with --all nonparametric_by_model_all.md and .csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dashboard import data                                    # noqa: E402
from etl.common import DEFAULT_DB, file_header                # noqa: E402
from scripts import nonparametric_tests as npt                # noqa: E402

OUT_DIR = ROOT / "output" / "reports"
MODELS = ("VADER+FinBERT", "VADER", "FinBERT")
CONTENT_TYPES = ("Post", "Comment")


def model_frame(db, model, ticker, start, end, communities):
    """The hours of `ticker` that have a Sentiment Score of the market under `model` and a price: sentiment_mean, the majority status and the six targets."""
    sent = data.global_hourly(db, start, end, communities, model, "all", CONTENT_TYPES)
    senti = data.sentiment_frame(sent, start, end)[["hour_utc", "sentiment_mean", "texts", "majority"]].rename(columns={"majority": "majority_final_status"})
    prices = data.price_series_for(db, (ticker,), start, end)[["hour_utc", *npt.TARGETS]]
    return senti.dropna(subset=["sentiment_mean"]).merge(prices, on="hour_utc", how="inner").sort_values("hour_utc").reset_index(drop=True)


def one_model(frame, boot, shifts, rng):
    rows = []
    for target in npt.TARGETS:
        sub = frame[["hour_utc", "sentiment_mean", "majority_final_status", target]].dropna(subset=["sentiment_mean", target])
        if len(sub) < npt.MIN_ROWS:
            continue
        x, y = sub.sentiment_mean.to_numpy(float), sub[target].to_numpy(float)
        days = (sub.hour_utc.to_numpy() // 86400).astype(int)
        rho, low, high, shift_p, formula_p = npt.spearman_block(x, y, days, rng, boot, shifts)
        rows.append({"target": npt.TARGET_LABEL[target], "n": len(sub), "spearman_rho": rho, "ci_low": low, "ci_high": high, "p_formula": formula_p,
                     "p_shift": shift_p, "pearson_r": float(stats.pearsonr(x, y)[0]), **npt.group_tests(y, sub.majority_final_status.to_numpy())})
    return pd.DataFrame(rows)


def check_against_panels(db, frame, ticker):
    """The combined model rebuilt from the sums must give the rows of the panel Global of the table `panels`: same n and same Spearman rho for the Current Return."""
    panel = npt.load(db)
    panel = panel[panel.ticker == ticker].dropna(subset=["sentiment_mean", "log_return"])
    mine = frame.dropna(subset=["sentiment_mean", "log_return"])
    both = panel.merge(mine, on="hour_utc", suffixes=("_panel", "_rebuilt"))
    return {"n_panel": len(panel), "n_rebuilt": len(mine), "n_both": len(both),
            "rho_panel": float(stats.spearmanr(panel.sentiment_mean, panel.log_return)[0]),
            "rho_rebuilt": float(stats.spearmanr(mine.sentiment_mean, mine.log_return)[0]),
            "max_abs_diff_sentiment": float((both.sentiment_mean_panel - both.sentiment_mean_rebuilt).abs().max()) if len(both) else float("nan")}


def run_all(args, start, end, communities):
    """Every asset x target x model: the sentiment of the market is built once per model, the prices of all the assets once.  Writes nonparametric_by_model_all.md/.csv:
    how many pairs each model makes significant, how much the three models agree (rank correlation of the rho of the pairs, share with the same sign) and the table of the
    Current Return per asset."""
    rng = np.random.default_rng(npt.SEED)
    universe = list(data.tickers(args.db).ticker)
    prices = data.price_series_for(args.db, tuple(universe), start, end)[["ticker", "hour_utc", *npt.TARGETS]]
    rows = []
    for model in MODELS:
        sent = data.global_hourly(args.db, start, end, communities, model, "all", CONTENT_TYPES)
        senti = data.sentiment_frame(sent, start, end)[["hour_utc", "sentiment_mean", "majority"]].rename(columns={"majority": "majority_final_status"}).dropna(subset=["sentiment_mean"])
        for ticker in universe:
            frame = senti.merge(prices[prices.ticker == ticker].drop(columns="ticker"), on="hour_utc", how="inner").sort_values("hour_utc")
            part = one_model(frame, args.boot, args.shifts, rng)
            rows.append(part.assign(model=model, ticker=ticker))
            print("done", model, ticker, flush=True)
    table = pd.concat(rows, ignore_index=True)
    for col in ("p_formula", "p_shift", "mw_p", "kw_p"):
        table[col + "_bh"] = npt.bh(table[col])
    wide = table.pivot_table(index=["ticker", "target"], columns="model", values="spearman_rho")
    lines = ["# การทดสอบ non-parametric ทุกสินทรัพย์ × ทุกแบบจำลองความรู้สึก", "",
             *file_header("เทียบผลสหสัมพันธ์อันดับ Spearman (block bootstrap, circular-shift), Mann-Whitney และ Kruskal-Wallis ของ 34 สินทรัพย์ × 6 ช่วงเวลา ระหว่างแบบจำลอง "
                          "VADER+FinBERT / VADER / FinBERT ว่าผลขึ้นกับแบบจำลองหรือไม่", "scripts/nonparametric_by_model.py",
                          "python scripts/nonparametric_by_model.py --all --boot %d --shifts %d" % (args.boot, args.shifts),
                          "reddit_hourly_global + market_hourly_features ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ความรู้สึก = คะแนนเฉลี่ยของทุกข้อความของตลาด (panel Global) ในชั่วโมงนั้น · bootstrap %d รอบ, เลื่อนวงกลม %d ครั้ง · p(BH) ปรับทั้งชุด %d คู่ (สินทรัพย์ × ช่วงเวลา × แบบจำลอง) · "
             "วิธีดู `nonparametric_tests.md`" % (args.boot, args.shifts, len(table)), "",
             "## 1) แต่ละแบบจำลองทำให้กี่คู่มีนัยสำคัญ", "",
             "| แบบจำลอง | คู่ที่ทดสอบ | Spearman p-formula < 0.05 | p-shift < 0.05 | p-shift(BH) < 0.05 | ช่วงเชื่อมั่นไม่คร่อม 0 | มัธยฐาน \|ρ\| | Mann–Whitney p(BH) < 0.05 | Kruskal–Wallis p(BH) < 0.05 |", "|---|---|---|---|---|---|---|---|---|"]
    for model in MODELS:
        t = table[table.model == model]
        lines.append("| %s | %d | %d | %d | %d | %d | %.4f | %d | %d |" % (model, len(t), int((t.p_formula < 0.05).sum()), int((t.p_shift < 0.05).sum()), int((t.p_shift_bh < 0.05).sum()),
                                                                          int(((t.ci_low > 0) | (t.ci_high < 0)).sum()), t.spearman_rho.abs().median(), int((t.mw_p_bh < 0.05).sum()), int((t.kw_p_bh < 0.05).sum())))
    lines += ["", "## 2) แบบจำลองทั้งสามให้ผลสอดคล้องกันแค่ไหน (เทียบ Spearman ρ ของแต่ละคู่ สินทรัพย์ × ช่วงเวลา)", "",
              "| คู่แบบจำลอง | จำนวนคู่ | สหสัมพันธ์อันดับของ ρ | ทิศ (+/−) เหมือนกัน | ต่างกันมากสุด \|Δρ\| |", "|---|---|---|---|---|"]
    for a, b in (("VADER+FinBERT", "VADER"), ("VADER+FinBERT", "FinBERT"), ("VADER", "FinBERT")):
        both = wide[[a, b]].dropna()
        lines.append("| %s เทียบ %s | %d | %+.3f | %.1f%% | %.3f |" % (a, b, len(both), stats.spearmanr(both[a], both[b])[0], 100 * float((np.sign(both[a]) == np.sign(both[b])).mean()),
                                                                     float((both[a] - both[b]).abs().max())))
    lines += ["", "## 3) Current Return รายสินทรัพย์ (Spearman ρ; ★ = p-shift(BH) < 0.05)", "",
              "| สินทรัพย์ | n | ρ VADER+FinBERT | ρ VADER | ρ FinBERT | ช่วงเชื่อมั่น VADER+FinBERT |", "|---|---|---|---|---|---|"]
    now = table[table.target == "Current Return"]
    for ticker in universe:
        cells = {r.model: r for r in now[now.ticker == ticker].itertuples()}
        if "VADER+FinBERT" not in cells:
            continue
        def cell(m):
            r = cells.get(m)
            return "-" if r is None else "%+.3f%s" % (r.spearman_rho, "★" if r.p_shift_bh < 0.05 else "")
        c = cells["VADER+FinBERT"]
        lines.append("| %s | %s | %s | %s | %s | %+.3f ถึง %+.3f |" % (ticker, "{:,}".format(c.n), cell("VADER+FinBERT"), cell("VADER"), cell("FinBERT"), c.ci_low, c.ci_high))
    lines += ["", "ตารางเต็มทุกคู่อยู่ใน `output/reports/nonparametric_by_model_all.csv`", ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "nonparametric_by_model_all.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT_DIR / "nonparametric_by_model_all.csv").open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ผล non-parametric ทุกสินทรัพย์ × ช่วงเวลา × แบบจำลองความรู้สึก (ข้อมูลชุดเดียวกับ nonparametric_by_model_all.md)",
                                         "scripts/nonparametric_by_model.py", "python scripts/nonparametric_by_model.py --all", "reddit_hourly_global + market_hourly_features", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--ticker", default="ES=F")
    parser.add_argument("--all", action="store_true", help="every asset x target x model (writes nonparametric_by_model_all.md/.csv)")
    parser.add_argument("--boot", type=int, default=1000)
    parser.add_argument("--shifts", type=int, default=2000)
    args = parser.parse_args(argv)
    info = data.data_range(args.db)
    start, end = int(info["reddit_lo"]), int(info["reddit_hi"])
    communities = tuple(dict.fromkeys(data.sources(args.db).subreddit))
    if args.all:
        return run_all(args, start, end, communities)
    rng = np.random.default_rng(npt.SEED)
    parts, frames = [], {}
    for model in MODELS:
        frames[model] = model_frame(args.db, model, args.ticker, start, end, communities)
        part = one_model(frames[model], args.boot, args.shifts, rng)
        parts.append(part.assign(model=model))
    table = pd.concat(parts, ignore_index=True)
    for col in ("p_formula", "p_shift", "mw_p", "kw_p"):
        table[col + "_bh"] = npt.bh(table[col])
    check = check_against_panels(args.db, frames["VADER+FinBERT"], args.ticker)

    name = args.ticker.replace("=", "_")
    lines = ["# การทดสอบ non-parametric ของ %s เทียบทุกแบบจำลองความรู้สึก" % args.ticker, "",
             *file_header("ผลสหสัมพันธ์อันดับ Spearman (ช่วงความเชื่อมั่น block bootstrap, p จาก circular-shift), Mann-Whitney U และ Kruskal-Wallis ของสินทรัพย์ %s "
                          "แยกตามแบบจำลองที่ให้คะแนนความรู้สึก (VADER+FinBERT / VADER / FinBERT) เพื่อดูว่าผลขึ้นกับแบบจำลองหรือไม่" % args.ticker,
                          "scripts/nonparametric_by_model.py", "python scripts/nonparametric_by_model.py --ticker %s --boot %d --shifts %d" % (args.ticker, args.boot, args.shifts),
                          "reddit_hourly_global + market_hourly_features ใน output/reddit.sqlite3 อ่านอย่างเดียว"), "",
             "ความรู้สึก = คะแนนเฉลี่ยของ **ทุกข้อความของตลาด** (panel Global, 6 ชุมชน, โพสต์ + คอมเมนต์) ในชั่วโมงนั้น เฉพาะชั่วโมงที่ %s มีราคา · "
             "วิธีและความหมายของคอลัมน์ดู `nonparametric_tests.md`" % args.ticker, "",
             "**ตรวจความถูกต้อง:** แบบจำลองรวมที่สร้างใหม่จากผลรวมรายชั่วโมงเทียบกับตาราง `panels` (panel Global): n %s เทียบ %s (ตรงกัน %s แถว) · Spearman ρ (Current Return) %+.4f เทียบ %+.4f · "
             "ความรู้สึกต่างกันมากสุด %.2e" % ("{:,}".format(check["n_rebuilt"]), "{:,}".format(check["n_panel"]), "{:,}".format(check["n_both"]), check["rho_rebuilt"], check["rho_panel"],
                                                check["max_abs_diff_sentiment"]), ""]
    for target in [npt.TARGET_LABEL[t] for t in npt.TARGETS]:
        sub = table[table.target == target]
        if sub.empty:
            continue
        lines += ["## %s" % ("Current Return (ผลตอบแทนชั่วโมงเดียวกับความรู้สึก)" if target == "Current Return" else "Future Return %s" % target), "",
                  "| แบบจำลอง | n | Spearman ρ | ช่วงเชื่อมั่น 95% | p-formula | p-shift | Pearson r | MW prob.sup. | MW p | KW ε² | KW p |", "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sub.itertuples():
            lines.append("| %s | %s | %+.4f | %+.4f ถึง %+.4f | %s | %s | %+.4f | %s | %s | %s | %s |" % (
                r.model, "{:,}".format(r.n), r.spearman_rho, r.ci_low, r.ci_high, npt.fmt_p(r.p_formula), npt.fmt_p(r.p_shift), r.pearson_r,
                "-" if pd.isna(r.mw_prob_superiority) else "%.3f" % r.mw_prob_superiority, npt.fmt_p(r.mw_p), "-" if pd.isna(r.kw_epsilon2) else "%.4f" % r.kw_epsilon2, npt.fmt_p(r.kw_p)))
        lines.append("")
    lines += ["หมายเหตุ: MW prob.sup. = ความน่าจะเป็นที่ชั่วโมงความรู้สึกบวกมีผลตอบแทนสูงกว่าชั่วโมงลบ (0.5 = ไม่ต่าง) · p ทุกค่าเป็นค่าบรรยาย (autocorrelation; การทดสอบหลายคู่) "
              "และตารางนี้เป็นสินทรัพย์เดียว จึงไม่ปรับ BH ข้ามสินทรัพย์", ""]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / ("nonparametric_by_model_%s.md" % name)).write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (OUT_DIR / ("nonparametric_by_model_%s.csv" % name)).open("w", newline="", encoding="utf-8") as sink:
        sink.write("\n".join(file_header("ผล non-parametric ของ %s แยกตามแบบจำลองความรู้สึก (ข้อมูลชุดเดียวกับ nonparametric_by_model_%s.md)" % (args.ticker, name),
                                         "scripts/nonparametric_by_model.py", "python scripts/nonparametric_by_model.py --ticker %s" % args.ticker,
                                         "reddit_hourly_global + market_hourly_features", comment=True)) + "\n")
        table.to_csv(sink, index=False)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
