"""Dashboard 7.1-1  Reddit Volume  (proposal 7.1: Reddit_volume, Volume Z-score).

Reddit_volume = ALL posts and comments of the 6 communities per hour.  The sidebar has the three dimensions of the
proposal: time, source (communities, Post / Comment) and asset (classes, several tickers).  With every ticker kept
(the default) the page shows all texts; when the asset filter keeps only some tickers it shows how often those are
mentioned instead (Ticker_mention_count of FactRedditVolume, split by Post / Comment) and says so on the page.
Data: reddit_volume_hourly (totals), FactRedditVolume (mentions), reddit_hourly_features (stored Z-score).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common  # noqa: E402
from dashboard.common import q  # noqa: E402

common.setup("Reddit Volume (ปริมาณโพสต์และความคิดเห็น)", "💬")
_, start, end, _ = common.sidebar(sources=True, multi=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
tickers = common.selected_tickers()
restricted = common.tickers_restricted()
if not src_ids or not tickers:
    common.nothing_selected(["Reddit Volume รวม", "เฉลี่ยต่อชั่วโมง", "ชั่วโมงที่ปริมาณสูงสุด", "Reddit Volume Z-score สูงสุด",
                             "ชั่วโมงที่ Z-score > 1.5"])

everything = q("total_volume_series", start, end, src_ids)      # all texts of the chosen sources (also the base of the rate)
if everything.empty:
    st.warning("ไม่มีข้อมูล Reddit ในช่วงนี้")
    st.stop()
if not restricted:
    total = everything
    count_name = "Reddit Volume"
else:
    # only some tickers kept: Ticker_mention_count split by Post / Comment; the Z-score follows `data.ticker_zscore`
    mentions = q("ticker_volume_series", tickers, start, end, src_ids).rename(columns={"mentions": "texts"})
    z = q("ticker_zscore", tickers, start, end, src_ids)[["hour_utc", "zscore", "basis"]]
    total = mentions.drop(columns="time").merge(z, on="hour_utc", how="outer").assign(
        time=lambda d: pd.to_datetime(d.hour_utc, unit="s", utc=True)).sort_values("time")
    count_name = "Ticker Mention Count"
# a missing hour means "no texts", which is a real 0 for a count (unlike sentiment, where it is unknown)
full = pd.DataFrame({"time": pd.date_range(everything.time.min(), everything.time.max(), freq="h")})
total = full.merge(total, on="time", how="left").fillna({"posts": 0, "comments": 0, "texts": 0})
shown = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum", "zscore": "max"}, how)

# KPI cards (proposal 7.1: Reddit_volume total / per hour / busiest hour, Volume Z-score peak and spike hours)
cards = [(count_name + " รวม", "{:,}".format(int(total.texts.sum())),
          "โพสต์ + ความคิดเห็น" if not restricted else "จำนวนครั้งที่หลักทรัพย์ที่เลือกถูกพูดถึงในแหล่งข้อมูลที่เลือก"),
         ("เฉลี่ยต่อชั่วโมง", "{:,.0f}".format(total.texts.mean()), None),
         ("ชั่วโมงที่ปริมาณสูงสุด", "{:,}".format(int(total.texts.max())), str(total.loc[total.texts.idxmax(), "time"])[:16] + " UTC"),
         ("Reddit Volume Z-score สูงสุด" if not restricted else "Volume Z-score ของที่เลือก สูงสุด", common.money(total.zscore.max()),
          "Z-score ของชั่วโมงที่ปริมาณสูงผิดปกติที่สุดในช่วงที่เลือก คือสูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้ากี่เท่าของส่วนเบี่ยงเบนมาตรฐาน"),
         ("ชั่วโมงที่ Z-score > 1.5", "{:,}".format(int((total.zscore > 1.5).sum())),
          "Spike คือชั่วโมงที่ปริมาณสูงกว่าค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้าเกิน 1.5 เท่าของส่วนเบี่ยงเบนมาตรฐาน (เกณฑ์ 1.5 ตาม proposal)")]
if restricted:
    base = float(everything.texts.sum())
    cards.append(("Ticker Mention Rate (%)", "n/a" if not base else "{:.3f}".format(100.0 * total.texts.sum() / base),
                  "Ticker Mention Count ÷ ปริมาณโพสต์และความคิดเห็นทั้งหมดของแหล่งข้อมูลเดียวกัน × 100"))
common.kpi_cards(cards)
if restricted:
    st.info("เลือกหลักทรัพย์บางตัว จึงแสดง**จำนวนครั้งที่หลักทรัพย์เหล่านั้นถูกพูดถึง** (Ticker_mention_count) แทนข้อความทั้งหมด "
            "ข้อความเดียวที่พูดถึงหลายตัวหรือหลายครั้งนับหลายครั้ง ติ๊กให้ครบทุกตัวเพื่อกลับไปดูข้อความทั้งหมด")
    basis = total["basis"].dropna()
    st.caption("Z-score คำนวณจาก%s" % ("จำนวนข้อความที่พูดถึงสินทรัพย์ (ค่าที่เก็บไว้ ใช้ใน panel_Ticker_spike)"
                                       if basis.empty or basis.iloc[0] == "texts" else
                                       "จำนวนครั้งที่ถูกพูดถึงรวมของที่เลือกในแหล่งข้อมูลที่เลือก (กฎเดียวกัน: เทียบ 24 ชั่วโมงก่อนหน้า) เพราะไม่ได้เก็บจำนวนข้อความต่อแหล่งข้อมูล"))

# Comments and posts are two charts one above the other (no dual axis: posts are only ~1 % of the texts, so a shared
# axis hides them and two axes make the lines cross meaninglessly).  A day without any text in the six communities is
# a data gap and is drawn as a gap, not as 0.
daily = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum"}, "Daily")
daily[["posts", "comments"]] = daily[["posts", "comments"]].where(daily.texts > 0)
hourly = total
common.show(common.count_chart(daily, hourly, "comments", "ความคิดเห็น" if not restricted else "พูดถึงในความคิดเห็น", common.C_REDDIT, how, bar=common.kind(st, "v_comments")), width="stretch")
common.show(common.count_chart(daily, hourly, "posts", "โพสต์" if not restricted else "พูดถึงในโพสต์", common.C_REDDIT_LIGHT, how, bar=common.kind(st, "v_posts")), width="stretch")
st.caption(common.count_caption(how))

# Z-score of the hourly volume; for day / week / month / year each point is the HIGHEST hourly Z-score of that period
z = common.line(shown, "time", "zscore", "Volume Z-score" + ("" if not restricted else " ของที่เลือก") + ("" if how == "Hourly" else " (สูงสุดของ%s)" % common.PERIOD_LABEL[how]),
                common.C_Z, dots=how != "Hourly", label="Z-score สูงสุด", bar=common.kind(st, "v_z"))
zero = common.zero_rule()       # Z = 0: normal volume
rule = common.ref_rule(1.5)
common.show(z + zero + rule, width="stretch")
st.caption("เส้นแดงคือ Z-score ของปริมาณ เทียบกับ 24 ชั่วโมงก่อนหน้า" + ("" if how == "Hourly" else "  \nค่าของแต่ละจุดคือชั่วโมงที่สูงที่สุดในช่วงนั้น") + "  \n"
           "เส้นทึบสีเทาคือระดับ 0 (ปริมาณปกติ)  \n"
           "เส้นประคือระดับ 1.5 หากเส้นแดงอยู่เหนือเส้นนี้ ถือว่าปริมาณสูงผิดปกติ (spike)")

if not restricted:
    by_source = q("total_volume_by_source", start, end, src_ids)
    subtitle = "แยกตามชุมชน"
else:
    by_source = q("volume_by_source", tickers, start, end, src_ids).rename(columns={"mentions": "texts"})
    subtitle = "แยกตามชุมชน (จำนวนครั้งที่หลักทรัพย์ที่เลือกถูกพูดถึง)"
pivot = by_source.pivot_table(index="subreddit", columns="content_type", values="texts", aggfunc="sum").fillna(0)
pivot["รวม"] = pivot.sum(axis=1)
st.subheader(subtitle)
common.table(pivot.sort_values("รวม", ascending=False).astype(int).rename(
    columns={"Comment": "ความคิดเห็น", "Post": "โพสต์"}), width="stretch")
