"""Numbers the dashboard shows when the filters are the full range (all communities, all tickers), for the book's
"management questions" paragraphs of 7.1 and 7.2.  It calls the SAME functions as the pages (dashboard.data), read-only.

Usage:  python scripts/dashboard_answers.py [--db output/reddit.sqlite3]
Output: output/reports/dashboard_answers.md
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd                                    # noqa: E402
from scipy import stats                                # noqa: E402

from dashboard import data                             # noqa: E402
from etl.common import DEFAULT_DB, file_header         # noqa: E402

OUT = ROOT / "output" / "reports" / "dashboard_answers.md"


def md(frame):
    cols = list(frame.columns)
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in frame.iterrows():
        rows.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(rows)


def volume(db, lo, hi):
    """Page 1 (Reddit Volume): the 5 cards, plus the trend (monthly totals, day order vs daily volume)."""
    total = data.total_volume_series(db, lo, hi)
    full = pd.DataFrame({"time": pd.date_range(total.time.min(), total.time.max(), freq="h")})
    total = full.merge(total, on="time", how="left").fillna({"posts": 0, "comments": 0, "texts": 0})
    peak = total.loc[total.texts.idxmax()]
    cards = pd.DataFrame([("Reddit Volume รวม", "{:,}".format(int(total.texts.sum()))),
                          ("เฉลี่ยต่อชั่วโมง", "{:,.0f}".format(total.texts.mean())),
                          ("ชั่วโมงที่สูงสุด", "{:,} ({} UTC)".format(int(peak.texts), str(peak.time)[:16])),
                          ("Z-score สูงสุด", "%.2f" % total.zscore.max()),
                          ("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((total.zscore > 1.5).sum())))], columns=["การ์ด", "ค่า"])
    daily = total.set_index("time").texts.resample("D").sum()
    daily = daily[daily > 0]
    rho, p = stats.spearmanr(range(len(daily)), daily.to_numpy())
    monthly = total.set_index("time").texts.resample("MS").sum().astype(int).rename("ปริมาณ").reset_index()
    monthly["time"] = monthly.time.dt.strftime("%Y-%m")
    return cards, monthly, (rho, p, len(daily))


def sentiment_ranking(db, lo, hi, min_texts=1000):
    """Page 4 (Market and Sentiment), ranking table: same rule as the page - the Sentiment Score of every ticker over the
    hours that have text, weighted by the number of texts; only tickers with >= min_texts texts are ranked."""
    names = list(dict.fromkeys(data.sources(db).subreddit))
    tickers = tuple(data.tickers(db).ticker)
    sent = data.sentiment_hourly(db, tickers, lo, hi, tuple(names), "VADER+FinBERT", "all", data.CONTENT_TYPES)
    frame = data.sentiment_frame(sent, lo, hi).dropna(subset=["sentiment_mean"])
    w = frame.texts
    frame = frame.assign(s=frame.sentiment_mean * w, p=frame.pos_ratio * w, n=frame.neg_ratio * w, w=w)
    out = frame.groupby("series", as_index=False)[["s", "p", "n", "w"]].sum()
    out = out.assign(sentiment=out.s / out.w, pos=100 * out.p / out.w, neg=100 * out.n / out.w)
    out["texts"] = out.w.astype(int)
    out["ranked"] = out.w >= min_texts
    return out.sort_values("sentiment", ascending=False)[["series", "texts", "sentiment", "pos", "neg", "ranked"]].round(4)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    db = parser.parse_args(argv).db
    sys.stdout.reconfigure(encoding="utf-8")
    rng = data.data_range(db)
    lo, hi = rng["reddit_lo"], rng["reddit_hi"]
    cards, monthly, (rho, p, n_days) = volume(db, lo, hi)
    rank = data.mention_ranking(db, lo, hi).head(10)
    rank = rank[["ticker", "big_group", "mentions", "texts_about", "mention_rate_pct"]].round(4)
    mlo, mhi = lo, hi                      # the page applies one date filter to both sides: use the Reddit range
    risk = data.group_risk(db, mlo, mhi).round(4)
    fr = data.future_return_by_group(db, mlo, mhi)
    fr = fr.assign(mean_return_pct=fr.mean_return_pct.round(5), share_up=fr.share_up.round(4)).sort_values(["big_group", "horizon"])
    snap = data.ticker_snapshot(db, mlo, mhi, ("BTC-USD",)).round(4)
    price = data.price_series_for(db, ("BTC-USD",), mlo, mhi)
    first, last = price.close.dropna().iloc[0], price.close.dropna().iloc[-1]
    ranking = sentiment_ranking(db, lo, hi)
    lines = ["# ตัวเลขที่ dashboard แสดง (ช่วงเต็ม ทุกชุมชน ทุกสินทรัพย์) สำหรับย่อหน้าตอบคำถามผู้บริหาร 7.1 และ 7.2", "",
             *file_header("ตัวเลขชุดเดียวกับที่หน้าจอ Reddit Volume, Ticker Mentions และ Price and Return แสดงเมื่อเลือกช่วงเต็ม",
                          "scripts/dashboard_answers.py", "python scripts/dashboard_answers.py",
                          "output/reddit.sqlite3 อ่านอย่างเดียว ผ่านฟังก์ชันของ dashboard/data.py"), "",
             "ช่วง Reddit: %s ถึง %s UTC  \nช่วงราคา: %s ถึง %s UTC" % (
                 pd.to_datetime(lo, unit="s"), pd.to_datetime(hi, unit="s"), pd.to_datetime(mlo, unit="s"),
                 pd.to_datetime(mhi, unit="s")), "",
             "## 7.1 Reddit Volume (การ์ด 5 ใบ)", "", md(cards), "",
             "แนวโน้ม (ส่วนขยาย): Spearman ระหว่างลำดับวันกับปริมาณรายวัน ρ = %.3f, p = %.3g, %d วัน" % (rho, p, n_days), "",
             "ปริมาณรายเดือน", "", md(monthly), "",
             "## 7.1 Ticker Mentions (10 อันดับแรก)", "", md(rank), "",
             "## 7.3 ความรู้สึกรายสินทรัพย์ (หน้า Market and Sentiment, ตารางจัดอันดับ; ranked = มีข้อความ >= 1,000)", "",
             md(ranking), "",
             "## 7.2 BTC-USD (ตัวอย่างข้อ 1)", "",
             "ราคาปิดแท่งแรก %.2f แท่งสุดท้าย %.2f (เปลี่ยน %.1f%%)" % (first, last, 100 * (last / first - 1)),
             "ปริมาณเฉลี่ยต่อชั่วโมง {:,.2f}".format(price.volume.mean()), "", md(snap), "",
             "## 7.2 ผลตอบแทนล่วงหน้าแยกกลุ่ม (ข้อ 2)", "", md(fr), "",
             "## 7.2 ความผันผวนแยกกลุ่ม (ข้อ 3)", "", md(risk), ""]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
