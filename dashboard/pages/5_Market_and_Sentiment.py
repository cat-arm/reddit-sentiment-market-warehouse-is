"""Dashboard 7.5-1  Market and Sentiment Overview  (proposal 7.5: close, volume, sentiment_mean, pos/neg/neu ratio,
majority status, Reddit_volume, Volume Z-score, Sentiment Momentum).

Dimensions of the dashboard (table 17): DimTime, DimTicker, DimSentimentSource, DimDetectionConfig, DimMajoritySentiment.  They are the
four blocks of the sidebar: time range and level; asset classes and tickers (several tickers are taken together);
communities of the sentiment source (and the model: VADER+FinBERT, VADER or FinBERT); majority status of the hour.
Sentiment here = EVERY text of the market (since 2026-11-15; it does not change when assets are unticked, and the page keeps its text side when no asset is
ticked).  It is recombined from `reddit_hourly_global` (sums per community), so any choice of communities is exact.  The ticked assets only decide the price
side (|Current Return|) and the ranking of the assets, which uses the texts that mention each asset.
Data: reddit_hourly_global, reddit_hourly_community, market_hourly_features.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from dashboard import common, data  # noqa: E402
from dashboard.common import GROUP_LABELS, q  # noqa: E402

common.setup("ตลาดและความรู้สึก (Market and Sentiment)", "🧭")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, detection="overview", majority=True)
how = common.granularity(start, end, "g_sent")
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
content_types = common.selected_content_types()
z_th = st.session_state.get("d_z", 0.0)                 # DimDetectionConfig: filters the hours (0 = no filter)
s_th = common.sentiment_cut()                           # a float (absolute) or the name of the signed variant
if not communities or not statuses or not content_types:
    common.nothing_selected(["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"],
                            "ยังไม่ได้เลือกชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
names = dict(zip(q("tickers").ticker, q("tickers").name))
asset_label = "" if not tickers else tickers[0] if one else "รวม %d ตัว" % len(tickers)
label = "ทั้งตลาด"                                                          # the text side: every text of the market

# ---- the text side: EVERY text of the market (not only those that mention the ticked assets); the price side: the ticked assets (hours with a valid bar)
prices = q("price_series_for", tickers, start, end) if tickers else pd.DataFrame()
sent = q("global_hourly", start, end, communities, common.selected_model(), common.text_variant(), content_types)      # the texts that pass the Sentiment Threshold
sent_all = q("global_hourly", start, end, communities, common.selected_model(), "all", content_types) if common.text_variant() != "all" else None   # the volume stays that of ALL the texts
market = q("market_zscore", start, end, common.sentiment_source_ids())    # the Z-score of ALL the texts of the hour (the proposal's Reddit_volume)
series_frame = data.sentiment_frame(sent, start, end, market=market, volume=sent_all)   # one series 'ALL': what the charts show


def rebased(df):
    """close and volume of every ticker as an index (first close = 100, mean volume = 100): comparable and averageable."""
    out = df[["ticker", "hour_utc", "time", "close", "volume"]].copy()
    out["abs_return"] = df.log_return.abs()                                  # the size of the move of each asset in the hour, before any average
    first = out.groupby("ticker").close.transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    mean_volume = out.groupby("ticker").volume.transform("mean")
    out["price_index"] = 100.0 * out.close / first
    out["volume_index"] = 100.0 * out.volume / mean_volume
    return out


if prices.empty:
    price_market = pd.DataFrame(columns=["hour_utc", "close", "volume", "abs_return"])
elif one:
    price_market = prices[["hour_utc", "close", "volume"]].assign(abs_return=prices.log_return.abs())
else:
    idx = rebased(prices)
    price_market = idx.groupby("hour_utc", as_index=False).agg(close=("price_index", "mean"), volume=("volume_index", "mean"),
                                                               abs_return=("abs_return", "mean"))     # the mean size of the move of the assets traded in the hour
series = series_frame.drop(columns="series").assign(time=pd.to_datetime(series_frame.hour_utc, unit="s", utc=True)).merge(price_market, on="hour_utc", how="left")
series["texts"] = series.texts.fillna(0)
series["sent_texts"] = series.sent_texts.fillna(0)                      # the texts the sentiment is made of (those that pass the Sentiment Threshold)
series = series.rename(columns={"texts": "reddit_volume", "majority": "majority_final_status"})

# hours whose majority status is not ticked lose every Reddit measure (price and market volume stay); no text = NULL
series = data.mask_majority(series, statuses)
# hours that do not meet the thresholds of DimDetectionConfig lose their Reddit measures too (0 / 0 = nothing removed)
series = data.mask_thresholds(series, z_th, 0.0)


def weighted_resample(df, how):
    """Sentiment of a day / week / month / year = mean of the hourly values weighted by the number of texts (hours with
    text only)."""
    if how == "Hourly":
        return df
    d = df.copy()
    has = d.sentiment_mean.notna()
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        d[col + "_w"] = (d[col] * d.sent_texts).where(has)
    d["texts_w"] = d.sent_texts.where(has)
    daily = d.set_index("time").resample(**common.RESAMPLE[how]).agg({
        "close": "last", "abs_return": "mean", "volume": "sum" if one else "mean", "reddit_volume": "sum", "zscore": "max", "momentum": "mean",
        **{c + "_w": "sum" for c in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio")}, "texts_w": "sum"})
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        daily[col] = (daily[col + "_w"] / daily["texts_w"]).where(daily["texts_w"] > 0)   # no text -> NULL, not 0
    return daily.reset_index()


shown = weighted_resample(series, how)
shown["abs_sentiment"] = shown.sentiment_mean.abs()                       # the size of the tilt of the texts (0 = neutral or the positives and negatives cancel), for the two charts below

# KPI cards first: the three KPIs of dashboard 1 (tables 15 and 17): Sentiment Score, Sentiment Momentum, Reddit Volume Z-score
w = series.sent_texts.where(series.sentiment_mean.notna())
common.kpi_cards([
    ("Sentiment Score", "n/a" if not w.sum() else "{:+.3f}".format((series.sentiment_mean * w).sum() / w.sum()),
     common.explain("ความรู้สึกเฉลี่ยของ Reddit ในช่วงนี้ ตั้งแต่ −1 (ลบมาก) ถึง +1 (บวกมาก) 0 = เป็นกลาง",
                    "คะแนนความรู้สึกของแต่ละข้อความตามแบบจำลองที่เลือก (ค่าเริ่มต้น VADER + FinBERT รวมผลตามกฎ) เฉลี่ยทุกข้อความที่เข้าเงื่อนไขของตัวกรอง ชั่วโมงที่มีข้อความมากมีน้ำหนักมาก")),
    ("Sentiment Momentum", common.money(series.momentum.mean()),
     common.explain("ความรู้สึกเปลี่ยนไปจากชั่วโมงก่อนหน้าเท่าไรโดยเฉลี่ย (+ = ดีขึ้น, − = แย่ลง)",
                    "ความรู้สึกเฉลี่ยชั่วโมงนี้ − ความรู้สึกเฉลี่ยชั่วโมงก่อน (ต้องมีข้อความทั้งสองชั่วโมง) แล้วเฉลี่ยทุกชั่วโมงในช่วงที่เลือก")),
    ("Reddit Volume Z-score สูงสุด", common.money(series.zscore.max()),
     common.explain("ชั่วโมงที่ปริมาณข้อความทั้งตลาดผิดปกติที่สุดในช่วงนี้ ผิดปกติแค่ไหน", common.Z_SCORE_HOW + " แล้วเลือกค่าสูงสุดของช่วง", common.REDDIT_Z_NOTE))])

# ---- (EXTENSION) the hourly mean of each model on its own: the final Sentiment Score (VADER + FinBERT after the rule that settles the conflicts) and the raw
# score of VADER and of FinBERT, so that one can see how far the two models agree (question 3 of the system 7.3).  The page filters apply (assets, time, communities,
# types of text, Sentiment Threshold); the model button of the sidebar does not: all three are always drawn.
MODEL_LINES = (("VADER+FinBERT", "ผลรวม (กฎรวมผล)", common.C_SENT), ("VADER", "VADER", "#555555"), ("FinBERT", "FinBERT", "#bcbd22"))


def model_series(model):
    sent_m = q("global_hourly", start, end, communities, model, common.text_variant(), content_types)
    frame = data.sentiment_frame(sent_m, start, end)[["hour_utc", "sentiment_mean", "texts"]]
    frame = frame.assign(time=pd.to_datetime(frame.hour_utc, unit="s", utc=True))
    weight = frame.texts.where(frame.sentiment_mean.notna())
    frame = frame.assign(sw=frame.sentiment_mean * weight, w=weight)
    if how != "Hourly":                                                   # a day / week / ...: the mean of the hours weighted by their number of texts
        frame = common.resample(frame[["time", "sw", "w"]], {"sw": "sum", "w": "sum"}, how)
        frame = frame.assign(sentiment_mean=(frame.sw / frame.w).where(frame.w > 0))
    frame.attrs["overall"] = float(sent_m.sentiment_sum.sum() / sent_m.texts.sum()) if len(sent_m) and sent_m.texts.sum() else float("nan")      # the mean of all the texts of the range
    return frame[["time", "sentiment_mean"]].copy().rename_axis(None)


by_model = {name: model_series(model) for model, name, _ in MODEL_LINES}
overall = {name: by_model[name].attrs.get("overall", float("nan")) for _, name, _ in MODEL_LINES}
common.block("ความรู้สึกเฉลี่ยรายชั่วโมงแยกตามแบบจำลอง (%s)" % label,
             "ใช้ตรวจสอบว่าแบบจำลองแต่ละตัว (ผลรวม, VADER, FinBERT) ให้ความรู้สึกเฉลี่ยสอดคล้องกันเพียงใดในแต่ละช่วงเวลา")
ticks = st.columns(len(MODEL_LINES))
visible = [(name, color) for (model, name, color), cell in zip(MODEL_LINES, ticks)
           if cell.checkbox("%s (%s)" % (name, common.COLOR_NAMES.get(color, "เทาเข้ม" if color == "#555555" else "เขียวมะกอก")), value=True, key="ms_" + model)]
if not visible:
    st.info("เลือกแสดงอย่างน้อย 1 เส้น")
elif all(by_model[name].sentiment_mean.notna().sum() == 0 for name, _ in visible):
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้" % label)
else:
    long = pd.concat([by_model[name].assign(model=name) for name, _ in visible], ignore_index=True).dropna(subset=["sentiment_mean"])
    how_ticks = {"tickCount": common.TICK_STEP[how]} if how in common.TICK_STEP else {}
    lines = alt.Chart(long).mark_line(opacity=0.85).encode(
        x=alt.X("time:T", title=None, axis=alt.Axis(format=common.DATE_FORMAT[how], labelOverlap=True, **how_ticks)),
        y=alt.Y("sentiment_mean:Q", title="Sentiment Score (เฉลี่ยของชั่วโมง)", axis=alt.Axis(format="+.2f")),
        color=alt.Color("model:N", scale=alt.Scale(domain=[n for n, _ in visible], range=[c for _, c in visible]), legend=None))
    hover = alt.Chart(long).mark_circle(size=150, opacity=0).encode(
        x="time:T", y="sentiment_mean:Q", color=alt.Color("model:N", scale=alt.Scale(domain=[n for n, _ in visible], range=[c for _, c in visible]), legend=None),
        tooltip=[alt.Tooltip("time:T", title=common.PERIOD_LABEL[how], format=common.DATE_TIP[how]), alt.Tooltip("model:N", title="แบบจำลอง"), alt.Tooltip("sentiment_mean:Q", title="Sentiment Score", format="+.3f")])
    common.show((lines + hover + common.zero_rule()).properties(height=common.CHART_HEIGHT), width="stretch")
    both = by_model["VADER"].merge(by_model["FinBERT"], on="time", suffixes=("_v", "_f")).dropna()
    agree = "n/a" if len(both) < 3 else "{:+.2f}".format(both.sentiment_mean_v.corr(both.sentiment_mean_f))

common.block("|Current Return| เทียบ |Sentiment Score| เฉลี่ยทั้งตลาด (%s)" % (asset_label or "ยังไม่ได้เลือกสินทรัพย์"),
             "ใช้ตรวจสอบว่าราคาขยับแรงเพียงใด ในช่วงที่ความรู้สึกของ Reddit เอนเอียงแรงหรือเบา (ไม่คำนึงทิศทางขึ้นหรือลง และบวกหรือลบ) ติ๊กออกเพื่อพิจารณาทีละเส้น",
             how="|Current Return| = ขนาดของ ln(ราคาปิดชั่วโมงนี้ ÷ ราคาปิดชั่วโมงก่อน) × 100 · |Sentiment Score| = ขนาดของค่าเฉลี่ยความรู้สึกของข้อความในชั่วโมงนั้น "
                 "ค่าสูง = ข้อความเอนเอียงไปทางเดียวกันแรง (บวกหรือลบก็ได้) ค่าใกล้ 0 = เป็นกลางหรือบวกกับลบหักล้างกัน")
price_col = "abs_return"
if prices.empty:                                   # no asset (or no price in the range): the sentiment line stays, the |Current Return| line has nothing to draw
    st.info("ยังไม่ได้เลือกสินทรัพย์ (หรือไม่มีราคาในช่วงนี้) จึงแสดงเฉพาะความรู้สึกเฉลี่ย")
    common.show(common.line(shown, "time", "abs_sentiment", "|Sentiment Score|", common.C_SENT, label="|Sentiment Score|", y_zero=True), width="stretch")
elif shown.sentiment_mean.notna().sum() == 0:
    st.info("ไม่มีข้อความในช่วงนี้ จึงแสดงเฉพาะ |Current Return|")
    common.show(common.line(shown, "time", price_col, "|Current Return| (%)", y_zero=True), width="stretch")
else:
    common.dual_chart(shown, "time", price_col, "abs_sentiment", "|Current Return| (%)", "|Sentiment Score|", "s_price_sent", "|Current Return|", "|Sentiment Score|",
                      left_fmt=".3f", left_zero=True, right_fmt=".3f", right_zero=True)

if shown.sentiment_mean.notna().sum() > 0:
    common.block("Reddit Volume เทียบ |Sentiment Score| เฉลี่ย (%s)" % label,
                 "ใช้ตรวจสอบว่าช่วงที่ Reddit มีการพูดคุยมาก ความรู้สึกของข้อความเอนเอียงแรงขึ้นหรือไม่ (ไม่คำนึงว่าบวกหรือลบ) ติ๊กออกเพื่อพิจารณาทีละเส้น",
                 how="Reddit Volume = จำนวนข้อความของชั่วโมงนั้น · |Sentiment Score| = ขนาดของค่าเฉลี่ยความรู้สึกของข้อความในชั่วโมงนั้น "
                     "ค่าสูง = ข้อความเอนเอียงไปทางเดียวกันแรง ค่าใกล้ 0 = เป็นกลางหรือบวกกับลบหักล้างกัน")
    common.dual_chart(shown, "time", "reddit_volume", "abs_sentiment", "Reddit Volume (จำนวนข้อความ)", "|Sentiment Score|", "s_z_sent",
                      "Reddit Volume", "|Sentiment Score|", left_color=common.C_REDDIT, left_fmt=",.0f", right_fmt=".3f", right_zero=True)

# ---- (EXTENSION) does the return rise when the sentiment rises, and fall when it falls?  The Sentiment Score of every hour that passes the filters (time, communities, model,
# Sentiment Threshold, Reddit Volume Z-score Threshold, majority status) against the mean Current Return of the ticked assets in the same hour (one row per hour: the market sentiment is
# one value per hour, so it is not repeated for every asset).  The hours are cut into ten equal groups by their sentiment; every number follows the filters of the sidebar.
SHOW_RELATION_BLOCK = False                                                  # the block is hidden (user, 2026-11-16: "เอาออกไป"); True brings it back
if SHOW_RELATION_BLOCK and not prices.empty and series.sentiment_mean.notna().any():
    hourly_return = prices.dropna(subset=["log_return"]).groupby("hour_utc", as_index=False).log_return.mean()
    rel = series[["hour_utc", "sentiment_mean", "momentum"]].merge(hourly_return, on="hour_utc").dropna(subset=["sentiment_mean"])
    result = common.relation_check(rel)
    common.block("ผลตอบแทนเฉลี่ยตามระดับความรู้สึก (แบ่งเป็น 10 กลุ่ม)",
                 "ใช้ตรวจสอบว่าชั่วโมงที่ Reddit อารมณ์ดี ราคาขึ้นตามไหม และชั่วโมงที่อารมณ์แย่ ราคาลงตามไหม (ชั่วโมงเดียวกัน)",
                 how="เรียงทุกชั่วโมงตามความรู้สึกของ Reddit จากแย่ไปดี แล้วแบ่งเป็น 10 กลุ่มเท่า ๆ กัน กลุ่มละ 10% ของชั่วโมง (กลุ่ม 1 = ชั่วโมงที่อารมณ์แย่ที่สุด, กลุ่ม 10 = ดีที่สุด ช่วงคะแนนของแต่ละกลุ่มอยู่ในตารางใต้กราฟ) · "
                     "แท่ง = ผลตอบแทนเฉลี่ยของสินทรัพย์ที่เลือก (เฉลี่ยเท่ากันทุกตัว) ในชั่วโมงของกลุ่มนั้น (เขียว = ขึ้น, แดง = ลง) · "
                     "เส้นดำ = ช่วงที่ค่าเฉลี่ยแกว่งได้ (ช่วงเชื่อมั่น 95% สุ่มทั้งวันใส่คืน 300 รอบ เพราะชั่วโมงติดกันคล้ายกัน) ถ้าเส้นคร่อม 0 แยกไม่ออกจากความบังเอิญ · "
                     "แท่งไล่จากแดงไปเขียว (ซ้าย → ขวา) = ความรู้สึกดีไปพร้อมกับราคาขึ้น · ตามตัวกรองทุกอย่างของแถบข้าง (ช่วงเวลา สินทรัพย์ ชุมชน แบบจำลอง เกณฑ์ Sentiment Score และ Reddit Volume)")
    table = result["decile"]
    if table is None:
        st.info("ข้อมูลไม่พอสำหรับแบ่งเป็น 10 กลุ่ม (ต้องมีชั่วโมงที่ผ่านตัวกรองอย่างน้อยราว 100 ชั่วโมง ขยายช่วงเวลาหรือลดเกณฑ์)")
    else:
        level, change = result["level"], result["change"]
        common.kpi_cards([
            ("ผลตอบแทนต่างกัน กลุ่มสูงสุด − ต่ำสุด", "{:+.3f}%".format(table["diff"]),
             common.explain("ถ้าเลือกเฉพาะชั่วโมงที่ความรู้สึกสูงสุด 10% เทียบกับต่ำสุด 10% ผลตอบแทนชั่วโมงเดียวกันต่างกันเท่าไร (บวก = ความรู้สึกสูงไปกับราคาขึ้น)",
                            "ผลตอบแทนเฉลี่ยของกลุ่ม 10 ลบผลตอบแทนเฉลี่ยของกลุ่ม 1 (หน่วย % ต่อชั่วโมง)",
                            "ช่วงเชื่อมั่น 95%%: %+.3f%% ถึง %+.3f%%" % table["diff_ci"] + (" (คร่อม 0 = แยกไม่ออกจากความบังเอิญ)" if table["diff_ci"][0] <= 0 <= table["diff_ci"][1] else ""))),
            ("กลุ่มความรู้สึกเรียงทิศเดียวกับผลตอบแทน", "{:+.2f}".format(table["trend"]),
             common.explain("แท่งทั้ง 10 เรียงขึ้นหรือลงทิศเดียวไหม (+1 = เรียงขึ้นเรื่อย ๆ, 0 = ไม่มีรูปแบบ, −1 = เรียงลงเรื่อย ๆ)",
                            "Spearman ของลำดับกลุ่ม (1 ถึง 10) กับผลตอบแทนเฉลี่ยของกลุ่ม",
                            "ช่วงเชื่อมั่น 95%%: %+.2f ถึง %+.2f · Spearman ของความรู้สึกรายชั่วโมงกับผลตอบแทนโดยตรง ρ = %s (p เลื่อนวงกลม %s, %s ชั่วโมง)" % (
                                *table["trend_ci"], "n/a" if np.isnan(level[0]) else "%+.3f" % level[0], "n/a" if np.isnan(level[3]) else "%.3f" % level[3], "{:,}".format(level[4])))),
            ("Spearman ของ \"การเปลี่ยนแปลง\" ความรู้สึก", "n/a" if np.isnan(change[0]) else "{:+.3f}".format(change[0]),
             common.explain("ชั่วโมงที่ความรู้สึกเพิ่มขึ้นจากชั่วโมงก่อน ราคาชั่วโมงนั้นขึ้นด้วยไหม (+ = ไปทางเดียวกัน)",
                            "Spearman ของ Sentiment Momentum (ความรู้สึกชั่วโมงนี้ − ชั่วโมงก่อน) กับผลตอบแทนชั่วโมงเดียวกัน",
                            "n/a" if np.isnan(change[0]) else "ช่วงเชื่อมั่น 95%%: %+.3f ถึง %+.3f · p (เลื่อนวงกลม คิดว่าชั่วโมงติดกันคล้ายกัน) = %.3f · n = %s ชั่วโมง" % (change[1], change[2], change[3], "{:,}".format(change[4]))))])
        groups = pd.DataFrame({"กลุ่ม": range(1, len(table["means"]) + 1), "ผลตอบแทนเฉลี่ย (%)": table["means"], "ต่ำ": table["low"], "สูง": table["high"], "ชั่วโมง": table["counts"]})
        groups["ชื่อกลุ่ม"] = ["%d (ต่ำสุด)" % g if g == 1 else "%d (สูงสุด)" % g if g == len(groups) else str(g) for g in groups["กลุ่ม"]]
        base = alt.Chart(groups).encode(x=alt.X("ชื่อกลุ่ม:N", sort=list(groups["ชื่อกลุ่ม"]), title="กลุ่มความรู้สึก (ต่ำ → สูง)", axis=alt.Axis(labelAngle=0)))
        bars = base.mark_bar(opacity=0.85).encode(
            y=alt.Y("ผลตอบแทนเฉลี่ย (%):Q", title="ผลตอบแทนเฉลี่ยชั่วโมงเดียวกัน (%)", axis=alt.Axis(format="+.3f")),
            color=alt.condition(alt.datum["ผลตอบแทนเฉลี่ย (%)"] >= 0, alt.value("#2ca02c"), alt.value("#d62728")),
            tooltip=["ชื่อกลุ่ม", alt.Tooltip("ผลตอบแทนเฉลี่ย (%):Q", format="+.4f"), alt.Tooltip("ต่ำ:Q", title="ช่วงเชื่อมั่นต่ำ", format="+.4f"),
                     alt.Tooltip("สูง:Q", title="ช่วงเชื่อมั่นสูง", format="+.4f"), alt.Tooltip("ชั่วโมง:Q", title="จำนวนแถว", format=",")])
        interval = base.mark_rule(color="#222222").encode(y="ต่ำ:Q", y2="สูง:Q")
        common.show((bars + interval + common.zero_rule()).properties(height=common.CHART_HEIGHT), width="stretch")
        edges = table["edges"]
        scale = pd.DataFrame({"": ["ช่วงคะแนนความรู้สึกของกลุ่ม", "จำนวนแถว (ชั่วโมง)"],
                              **{str(g): ["%+.3f ถึง %+.3f" % (edges[g - 1], edges[g]), "{:,}".format(int(table["counts"][g - 1]))] for g in groups["กลุ่ม"]}})
        st.caption("กลุ่ม 1 = ความรู้สึกต่ำสุด · กลุ่ม %d = สูงสุด · คะแนนความรู้สึก −1 (ลบมาก) ถึง +1 (บวกมาก) 0 = เป็นกลาง" % len(groups))
        common.table(scale, hide_index=True, width="stretch")

common.block("สัดส่วนความคิดเห็นเชิงบวก ลบ และเป็นกลาง",
             "ใช้ตรวจสอบสัดส่วนของความรู้สึกแต่ละประเภท และการเปลี่ยนแปลงตามช่วงเวลา")
RATIO_MODES = ("ความคิดเห็นจริง (สัดส่วนข้อความ)", "ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)")
SHOW_VOTE_MODE = False                                                      # the vote mode is hidden (user, 2026-11-16); set True to bring the picker back
mode = (st.radio("นับสัดส่วนจาก", RATIO_MODES, horizontal=True, key="s_ratio_mode", label_visibility="collapsed")
        if SHOW_VOTE_MODE else RATIO_MODES[0])
COLORS = alt.Scale(domain=["บวก", "ลบ", "เป็นกลาง"], range=["#2ca02c", "#d62728", "#7f7f7f"])
if mode == RATIO_MODES[0]:
    ratios = shown.melt(id_vars="time", value_vars=["pos_ratio", "neg_ratio", "neu_ratio"], var_name="ประเภท",
                        value_name="สัดส่วน").dropna()
    ratios["ประเภท"] = ratios["ประเภท"].map({"pos_ratio": "บวก", "neg_ratio": "ลบ", "neu_ratio": "เป็นกลาง"})
else:
    votes = data.vote_shares(series, None if how == "Hourly" else common.RESAMPLE[how])
    ratios = votes.rename(columns={"share": "สัดส่วน"}).assign(ประเภท=lambda d: d.status.map(
        {"positive": "บวก", "negative": "ลบ", "neutral": "เป็นกลาง"}))
if not ratios.empty:
    area = (alt.Chart(ratios).mark_area().encode(
        x=alt.X("time:T", title=None), y=alt.Y("สัดส่วน:Q", stack="normalize", axis=alt.Axis(format="%")),
        color=alt.Color("ประเภท:N", scale=COLORS), tooltip=["time:T", "ประเภท", alt.Tooltip("สัดส่วน:Q", format=".1%")])
        .properties(height=common.CHART_HEIGHT))
    common.show(area, width="stretch")

# ---- which asset is the most positive / negative?  (management question 2 of 7.3): one row per ticked ticker
common.block("สินทรัพย์ใดมีความรู้สึกเป็นบวกหรือลบมากที่สุด",
             "ใช้ตรวจสอบว่าข้อความที่พูดถึงสินทรัพย์ใดมีความรู้สึกเฉลี่ยเป็นบวกหรือลบมากที่สุดในช่วงที่เลือก")
if len(tickers) < 2:
    st.info("เลือกสินทรัพย์อย่างน้อย 2 ตัวเพื่อเรียงอันดับเทียบกัน")
else:
    sent_t = q("sentiment_hourly", tickers, start, end, communities, common.selected_model(), common.text_variant(), content_types)       # the texts that mention each asset
    sent_t_all = q("sentiment_hourly", tickers, start, end, communities, common.selected_model(), "all", content_types) if common.text_variant() != "all" else None
    per_ticker = data.sentiment_frame(sent_t, start, end, market=market, volume=sent_t_all)        # one series per ticker
    passes = data.threshold_mask(per_ticker, z_th, 0.0) & per_ticker.majority.isin(statuses)      # the hours that pass the Reddit Volume Threshold and the majority filter
    has_text = per_ticker[passes].dropna(subset=["sentiment_mean"])
    weight = has_text.texts
    ranked = has_text.assign(
        s=has_text.sentiment_mean * weight, p=has_text.pos_ratio * weight, n=has_text.neg_ratio * weight, w=weight
    ).groupby("series", as_index=False)[["s", "p", "n", "w"]].sum()
    ranked = ranked[ranked.w > 0].assign(sentiment=lambda d: d.s / d.w, pos=lambda d: 100 * d.p / d.w, neg=lambda d: 100 * d.n / d.w)
    ranked = ranked.sort_values("sentiment", ascending=False)
    if ranked.empty:
        st.info("ไม่มีสินทรัพย์ที่มีข้อความในช่วงนี้")
    else:
        groups = dict(zip(q("tickers").ticker, q("tickers").big_group))
        ranked["กลุ่ม"] = ranked.series.map(lambda s: GROUP_LABELS.get(groups.get(s), ""))
        ranked.insert(0, "อันดับ", range(1, len(ranked) + 1))
        common.table(ranked[["อันดับ", "series", "กลุ่ม", "w", "sentiment", "pos", "neg"]].rename(columns={
            "series": "สินทรัพย์", "w": "จำนวนข้อความ", "sentiment": "Sentiment Score เฉลี่ย", "pos": "เชิงบวก (%)",
            "neg": "เชิงลบ (%)"}).round(3), hide_index=True, width="stretch", height=min(420, 60 + 36 * len(ranked)))

# ---- DimDetectionConfig drill-down: the hours that meet the thresholds of the sidebar, and what the price did next
