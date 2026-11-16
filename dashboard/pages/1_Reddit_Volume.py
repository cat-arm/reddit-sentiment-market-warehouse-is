"""Dashboard 7.1  Reddit Volume and Ticker Mentions  (proposal 7.1: Reddit_volume, Volume Z-score, Ticker_mention_count, Mention Rate).

One page for the one dashboard 7.1 of the proposal (it was two pages, 1 and 2, until 2026-11-15).  Two parts, one under the other:
  1. Reddit Volume of ALL the texts of the chosen sources (posts + comments): it never depends on the asset filter, so it does not disappear when a
     ticker is unticked.
  2. Ticker Mentions of the ticked tickers: count, rate, ranking and where they are mentioned.
The sidebar has the three dimensions of the proposal: time, source (communities, Post / Comment) and asset (classes, several tickers).  Every chart and
table has a title and one line saying what it is for; every chart is a line (no line / bar switch).
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


block = common.block


def community_overview(volume_by_source, mention_by_source=None):
    """ONE table by community: the message volume (total and share of the total) and, next to it, the volume of mentions of the ticked tickers (total and share)
    and the Ticker Mention Rate (%) of the community = its mentions / its message volume x 100.  No split into posts and comments.  A last row has the totals."""
    vol = volume_by_source.groupby("subreddit").texts.sum().sort_values(ascending=False)
    table = pd.DataFrame({"ปริมาณข้อความ": vol, "ปริมาณข้อความ (%)": 100.0 * vol / vol.sum()})
    if mention_by_source is not None and not mention_by_source.empty:
        men = mention_by_source.groupby("subreddit").mentions.sum().reindex(table.index).fillna(0)
        table["ปริมาณการกล่าวถึง"] = men
        table["ปริมาณการกล่าวถึง (%)"] = 100.0 * men / men.sum() if men.sum() else float("nan")
        table["Mention Rate (%)"] = 100.0 * men / vol.where(vol > 0)
    table.loc["รวมทุกชุมชน"] = table.sum()
    if "Mention Rate (%)" in table:
        table.loc["รวมทุกชุมชน", "Mention Rate (%)"] = 100.0 * table.loc["รวมทุกชุมชน", "ปริมาณการกล่าวถึง"] / table.loc["รวมทุกชุมชน", "ปริมาณข้อความ"]
    percent = {c: st.column_config.NumberColumn(format="%.1f") for c in table.columns if "%" in c}
    counts = {c: st.column_config.NumberColumn(format="localized") for c in table.columns if "%" not in c}
    st.dataframe(table, column_config={**counts, **percent}, width="stretch")


common.setup("ปริมาณข้อความและการกล่าวถึงสินทรัพย์ (Reddit Volume and Ticker Mentions)", "💬")
_, start, end, _ = common.sidebar(sources=True, multi=True)
how = common.granularity(start, end)
src_ids = common.selected_sources()
tickers = common.selected_tickers()
if not src_ids:
    common.nothing_selected(["Reddit Volume รวม", "เฉลี่ยต่อชั่วโมง", "ชั่วโมงที่ปริมาณสูงสุด", "Z-score สูงสุดในช่วง"])

everything = q("total_volume_series", start, end, src_ids)      # ALL the texts of the chosen sources (also the base of the mention rate)
if everything.empty:
    st.warning("ไม่มีข้อมูล Reddit ในช่วงนี้")
    st.stop()

# a missing hour means "no texts", which is a real 0 for a count (unlike sentiment, where it is unknown)
full = pd.DataFrame({"time": pd.date_range(everything.time.min(), everything.time.max(), freq="h")})
total = full.merge(everything, on="time", how="left").fillna({"posts": 0, "comments": 0, "texts": 0})
# a text counts ONCE for a ticker however many times it names it (user decision 2026-11-15); a text that names two ticked tickers counts for both
mentions = (q("ticker_texts_series", tickers, start, end, src_ids).rename(columns={"texts": "mentions"}) if tickers
            else pd.DataFrame(columns=["time", "mentions"]))
total = total.merge(mentions[["time", "mentions"]], on="time", how="left").fillna({"mentions": 0})      # nobody mentioned it = a real 0
# the Z-score of the texts that mention the ticked tickers (24 prior hours, current hour excluded: the rule of the volume Z-score)
mention_z = (q("ticker_zscore", tickers, start, end, src_ids)[["time", "zscore"]].rename(columns={"zscore": "mention_z"}) if tickers
             else pd.DataFrame(columns=["time", "mention_z"]))
total = total.merge(mention_z, on="time", how="left")
shown_total = common.resample(total, {"posts": "sum", "comments": "sum", "texts": "sum", "mentions": "sum", "zscore": "max", "mention_z": "max"}, how)
many = len(tickers) > 1
label = "สินทรัพย์ทั้งหมด" if not common.tickers_restricted() else ("" if not tickers else tickers[0] if not many else "%d ตัวรวมกัน" % len(tickers))

# ================================================================================================ 1. Reddit Volume (all texts)
# (no heading above the first cards: they open the page, directly under its title)
all_mentions = float(total.mentions.sum())
common.kpi_cards([
    ("ปริมาณข้อความรวม", "{:,}".format(int(total.texts.sum())), common.explain("จำนวนโพสต์และความคิดเห็นทั้งหมดใน Reddit ของชุมชนที่เลือก ในช่วงเวลาที่เลือก", "นับทุกข้อความที่ผ่านการคัดกรอง ไม่ว่าจะพูดถึงสินทรัพย์หรือไม่ (ไม่ขึ้นกับตัวกรองสินทรัพย์)")),
    ("เฉลี่ยต่อชั่วโมง", "{:,.0f}".format(total.texts.mean()),
     common.explain("ในหนึ่งชั่วโมง มีข้อความเฉลี่ยกี่ข้อความ", "ปริมาณข้อความรวม ÷ จำนวนชั่วโมงในช่วงเวลาที่เลือก (ชั่วโมงที่ไม่มีข้อความนับเป็น 0)")),
    ("ชั่วโมงที่ปริมาณสูงสุด", "{:,}".format(int(total.texts.max())), common.explain("ชั่วโมงที่คนคุยกันมากที่สุดในช่วงนี้", "หาชั่วโมงที่มีข้อความมากที่สุด ตัวเลขคือจำนวนข้อความในชั่วโมงนั้น ใต้ตัวเลขคือเวลา (UTC)")),
    ("Z-score สูงสุดในช่วง", common.money(total.zscore.max()),
     common.explain("ชั่วโมงที่ปริมาณข้อความผิดปกติที่สุดในช่วงนี้ ผิดปกติแค่ไหน", common.Z_SCORE_HOW + " แล้วเลือกค่าสูงสุดของช่วง", common.REDDIT_Z_NOTE)),
    ("ปริมาณการกล่าวถึงสินทรัพย์รวม", "{:,}".format(int(all_mentions)),
     common.explain("จำนวนข้อความที่พูดถึงสินทรัพย์ที่เลือก" + ((" (" + label + ")") if label else ""),
                    "นับข้อความที่พูดถึงสินทรัพย์ตัวนั้น ข้อความละ 1 ครั้งต่อสินทรัพย์ แม้พิมพ์ชื่อซ้ำหลายครั้ง ข้อความที่พูดถึงหลายตัวนับให้ทุกตัว")
     if label else "ยังไม่ได้เลือกหลักทรัพย์"),
    ("Ticker Mention Rate (%)", "n/a" if not total.texts.sum() or not tickers else "{:.3f}".format(100.0 * all_mentions / float(total.texts.sum())),
     common.explain("ในข้อความทั้งหมด มีกี่ % ที่พูดถึงสินทรัพย์ที่เลือก",
                    "ปริมาณการกล่าวถึงสินทรัพย์ ÷ ปริมาณข้อความรวม × 100 (สินทรัพย์ตัวเดียวไม่เกิน 100% เลือกหลายตัวอาจเกินได้ เพราะข้อความเดียวนับให้หลายตัว)"))])

block("ปริมาณข้อความ เทียบกับปริมาณการกล่าวถึงสินทรัพย์",
      "ใช้ตรวจสอบว่า Reddit มีการพูดคุยมากน้อยเพียงใดในแต่ละช่วงเวลา และเปรียบเทียบกับปริมาณการกล่าวถึงสินทรัพย์ที่เลือก",
      how="ปริมาณข้อความ = จำนวนโพสต์และความคิดเห็นทั้งหมด · ปริมาณการกล่าวถึงสินทรัพย์ = จำนวนข้อความที่พูดถึงสินทรัพย์ที่เลือก นับครั้งเดียวต่อสินทรัพย์ต่อข้อความ")
if tickers:       # two lines on two axes (the volume on the left, the mentions of the ticked tickers on the right), as the charts of Price and Reddit
    common.dual_chart(shown_total, "time", "texts", "mentions", "ปริมาณข้อความทั้งหมด", "ปริมาณการกล่าวถึงสินทรัพย์", "vm",
                      "ปริมาณข้อความทั้งหมด", "ปริมาณการกล่าวถึงสินทรัพย์", left_color=common.C_REDDIT, right_color=common.C_RATE,
                      left_fmt=",.0f", right_fmt=",.0f")
else:             # no ticker ticked: the volume line stays alone
    common.show(common.line(shown_total, "time", "texts", "ปริมาณข้อความทั้งหมด", common.C_REDDIT, fmt=common.DATE_FORMAT[how]), width="stretch")

# Z-score of the hourly volume and of the hourly mentions; for day / week / month / year each point is the HIGHEST hourly Z-score of that period
block("Z-score ปริมาณข้อความ เทียบกับ Z-score ปริมาณการกล่าวถึงสินทรัพย์",
      "ใช้ตรวจสอบชั่วโมงที่มีการพูดคุยสูงผิดปกติ และตรวจสอบว่าการกล่าวถึงสินทรัพย์ผิดปกติพร้อมกันหรือไม่ เส้นประคือเกณฑ์ spike (Z-score 1.5)",
      how="(ปริมาณของชั่วโมงนั้น − ค่าเฉลี่ยของ 24 ชั่วโมงก่อนหน้า) ÷ ส่วนเบี่ยงเบนมาตรฐาน (SD) ของ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน")
z_all = [("zscore", "Z-score ปริมาณข้อความ", common.C_REDDIT)] + ([("mention_z", "Z-score ปริมาณการกล่าวถึงสินทรัพย์", common.C_RATE)] if tickers else [])
z_boxes = st.columns([1, 1, 2])                                  # one tick box per line: untick a line to read the other alone
z_lines = [line for i, line in enumerate(z_all) if z_boxes[i].checkbox("%s (%s)" % (line[1], common.COLOR_NAMES[line[2]]), value=True, key="zl_" + line[0])]
if not z_lines:
    st.info("เลือกแสดงอย่างน้อย 1 เส้น")
    z_lines = z_all
z_long = pd.concat([shown_total[["time", col]].rename(columns={col: "value"}).assign(series=name) for col, name, _ in z_lines], ignore_index=True)
z_enc = dict(x=alt.X("time:T", title=None, axis=alt.Axis(format=common.DATE_FORMAT[how], labelOverlap=True,
                                                         **({"tickCount": common.TICK_STEP[how]} if how in common.TICK_STEP else {}))),
             y=alt.Y("value:Q", title="Z-score" + ("" if how == "Hourly" else " (สูงสุดของ%s)" % common.PERIOD_LABEL[how]), axis=alt.Axis(minExtent=55)),
             color=alt.Color("series:N", title=None, legend=None, scale=alt.Scale(domain=[n for _, n, _ in z_lines], range=[c for _, _, c in z_lines])))   # no legend: the tick boxes above name and colour the lines
z_tip = [alt.Tooltip("time:T", title=common.PERIOD_LABEL[how], format=common.DATE_TIP[how]), alt.Tooltip("series:N", title="ชุดข้อมูล"),
         alt.Tooltip("value:Q", title="Z-score สูงสุด", format=",.2f")]
z_chart = alt.layer(alt.Chart(z_long).mark_line().encode(**z_enc), alt.Chart(z_long).mark_circle(size=150, opacity=0).encode(tooltip=z_tip, **z_enc))
common.show(z_chart.properties(height=common.CHART_HEIGHT) + common.zero_rule() + common.ref_rule(1.5), width="stretch")

# ================================================================================================ the ticked tickers: ranking (under the comparison chart)
rank = pd.DataFrame()
if not tickers:
    st.info("ยังไม่ได้เลือกหลักทรัพย์ ติ๊กหลักทรัพย์ที่แถบด้านซ้ายเพื่อดูการถูกกล่าวถึง")
else:
    rank = q("mention_texts_ranking", start, end, src_ids)
    rank = rank[rank.ticker.isin(tickers)].reset_index(drop=True)
    if rank.empty or mentions.empty:
        st.warning("ไม่มีข้อมูลการกล่าวถึงในช่วงและตัวกรองที่เลือก")
    else:
        rank["กลุ่ม"] = rank.big_group.map(common.group_name)
        block("ปริมาณการกล่าวถึงสินทรัพย์", "ใช้ตรวจสอบว่าสินทรัพย์ใดถูกกล่าวถึงมากที่สุดในช่วงที่เลือก",
              how="นับจำนวนข้อความที่พูดถึงสินทรัพย์แต่ละตัวในช่วงที่เลือก ครั้งเดียวต่อสินทรัพย์ต่อข้อความ แสดง 15 อันดับแรก สีแสดงกลุ่มสินทรัพย์")
        chart = (alt.Chart(rank.head(15)).mark_bar().encode(
            x=alt.X("mentions:Q", title="ปริมาณการกล่าวถึง (ข้อความ)"),
            y=alt.Y("ticker:N", sort="-x", title=None, axis=alt.Axis(labelOverlap=False)),   # label every ticker
            color=alt.Color("กลุ่ม:N", title="กลุ่ม", scale=common.group_scale()),
            tooltip=["ticker", "กลุ่ม", alt.Tooltip("mentions:Q", format=","), alt.Tooltip("mention_rate_pct:Q", format=".3f")])
            .properties(height=380))
        common.show(chart, width="stretch")
        block("ปริมาณการกล่าวถึงสินทรัพย์ รายสินทรัพย์", "ใช้ตรวจสอบตัวเลขของแต่ละสินทรัพย์เทียบกับปริมาณข้อความทั้งหมด"),
        common.table(rank[["ticker", "กลุ่ม", "mentions", "total_volume", "mention_rate_pct", "peak_hour_texts"]].rename(columns={
            "mentions": "ปริมาณการกล่าวถึง", "total_volume": "ปริมาณข้อความทั้งหมด", "mention_rate_pct": "Ticker Mention Rate (%)",
            "peak_hour_texts": "สูงสุดใน 1 ชั่วโมง"}).round(3),
            hide_index=True, width="stretch", height=360)

# ================================================================================================ by community
block("ปริมาณข้อความและปริมาณการกล่าวถึงแยกตามชุมชน", "ใช้ตรวจสอบส่วนแบ่งของข้อความแต่ละชุมชน และสัดส่วนของข้อความที่พูดถึงสินทรัพย์ที่เลือก")
community_overview(q("total_volume_by_source", start, end, src_ids),
                   q("mention_texts_by_source", tickers, start, end, src_ids) if tickers else None)
