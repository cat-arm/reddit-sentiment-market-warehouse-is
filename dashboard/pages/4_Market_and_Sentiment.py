"""Dashboard 7.5-1  Market and Sentiment Overview  (proposal 7.5: close, volume, sentiment_mean, pos/neg/neu ratio,
majority status, Reddit_volume, Volume Z-score, Sentiment Momentum).

Dimensions of the dashboard (table 17): DimTime, DimTicker, DimSentimentSource, DimMajoritySentiment.  They are the
four blocks of the sidebar: time range and level; asset classes and tickers (several tickers are taken together);
communities of the sentiment source (the model is always VADER+FinBERT); majority status of the hour.
Sentiment here = only the texts that MENTION the chosen tickers.  It is recombined from `reddit_hourly_community`
(sums per community), so any choice of communities is exact; with every community ticked it equals the stored KPIs.
Several tickers: one combined series (texts of all of them summed, price as an index) plus a table per ticker.
Data: reddit_hourly_community, market_hourly_features.
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

common.setup("Market and Sentiment: ภาพรวมตลาดและความรู้สึก", "🧭")
_, start, end, _ = common.sidebar(multi=True, sentiment=True, majority=True)
how = common.granularity(start, end, "g_sent")
tickers = common.selected_tickers()
communities = common.selected_communities()
statuses = common.selected_statuses()
if not tickers or not communities or not statuses:
    common.nothing_selected(["Sentiment Score", "Sentiment Momentum", "Reddit Volume Z-score สูงสุด"],
                            "ไม่ได้เลือกหลักทรัพย์ ชุมชน หรือประเภทความรู้สึกส่วนใหญ่ จึงไม่มีข้อมูลแสดง")
one = len(tickers) == 1
names = dict(zip(q("tickers").ticker, q("tickers").name))
label = tickers[0] if one else "รวม %d ตัว" % len(tickers)

# ---- prices of the ticked tickers (hours with a valid bar) and the sentiment KPIs recombined from the chosen communities
prices = q("price_series_for", tickers, start, end)
sent = q("sentiment_hourly", tickers, start, end, communities, common.selected_model())
if prices.empty:
    st.info("ไม่มีข้อมูลราคาของหลักทรัพย์ที่เลือกในช่วงนี้ (ตลาดอาจปิด)")
    st.stop()
per_ticker = data.sentiment_frame(sent, start, end)                       # one series per ticker
series_frame = data.sentiment_frame(sent, start, end, combined=not one)   # what the charts show


def rebased(df):
    """close and volume of every ticker as an index (first close = 100, mean volume = 100): comparable and averageable."""
    out = df[["ticker", "hour_utc", "time", "close", "volume"]].copy()
    first = out.groupby("ticker").close.transform(lambda s: s.dropna().iloc[0] if s.notna().any() else np.nan)
    mean_volume = out.groupby("ticker").volume.transform("mean")
    out["price_index"] = 100.0 * out.close / first
    out["volume_index"] = 100.0 * out.volume / mean_volume
    return out


if one:
    market = prices[["hour_utc", "time", "close", "volume"]].copy()
else:
    idx = rebased(prices)
    market = idx.groupby("hour_utc", as_index=False).agg(time=("time", "first"), close=("price_index", "mean"),
                                                         volume=("volume_index", "mean"))
series = market.merge(series_frame.drop(columns="series"), on="hour_utc", how="left")
series["texts"] = series.texts.fillna(0)
series = series.rename(columns={"texts": "reddit_volume", "majority": "majority_final_status"})

# hours whose majority status is not ticked lose every Reddit measure (price and market volume stay); no text = NULL
series = data.mask_majority(series, statuses)


def weighted_resample(df, how):
    """Sentiment of a day / week / month / year = mean of the hourly values weighted by the number of texts (hours with
    text only)."""
    if how == "Hourly":
        return df
    d = df.copy()
    has = d.sentiment_mean.notna()
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        d[col + "_w"] = (d[col] * d.reddit_volume).where(has)
    d["texts_w"] = d.reddit_volume.where(has)
    daily = d.set_index("time").resample(**common.RESAMPLE[how]).agg({
        "close": "last", "volume": "sum" if one else "mean", "reddit_volume": "sum", "zscore": "max", "momentum": "mean",
        **{c + "_w": "sum" for c in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio")}, "texts_w": "sum"})
    for col in ("sentiment_mean", "pos_ratio", "neg_ratio", "neu_ratio"):
        daily[col] = (daily[col + "_w"] / daily["texts_w"]).where(daily["texts_w"] > 0)   # no text -> NULL, not 0
    return daily.reset_index()


shown = weighted_resample(series, how)

# KPI cards first: the three KPIs of dashboard 1 (tables 15 and 17): Sentiment Score, Sentiment Momentum, Reddit Volume Z-score
w = series.reddit_volume.where(series.sentiment_mean.notna())
common.kpi_cards([
    ("Sentiment Score", "n/a" if not w.sum() else "{:+.3f}".format((series.sentiment_mean * w).sum() / w.sum()),
     "ผลรวม final_sentiment ÷ จำนวนความคิดเห็น เฉลี่ยถ่วงน้ำหนักด้วยจำนวนข้อความของแต่ละชั่วโมง"),
    ("Sentiment Momentum", common.money(series.momentum.mean()), "(sentiment_mean ชั่วโมงนี้ − ชั่วโมงก่อนหน้า) เฉลี่ย"),
    ("Reddit Volume Z-score สูงสุด", common.money(series.zscore.max()), "เทียบ 24 ชั่วโมงก่อนหน้า ไม่รวมชั่วโมงปัจจุบัน")])

st.subheader("%s: ราคาปิดเทียบค่าความรู้สึกเฉลี่ย" % label)
price_col = "close"
if shown.sentiment_mean.notna().sum() == 0:
    st.info("ไม่มีข้อความที่พูดถึง %s ในช่วงนี้ จึงแสดงเฉพาะราคา" % label)
    st.altair_chart(common.line(shown, "time", price_col, "ราคาปิด (USD)" if one else "ราคาปิด ดัชนี (ค่าแรก = 100)",
                                bar=common.kind(st, "s_close")), width="stretch")
else:
    st.altair_chart(common.dual_axis(shown, "time", price_col, "sentiment_mean",
                                     "ราคาปิด (USD)" if one else "ราคาปิด ดัชนี (ค่าแรก = 100)", "Sentiment Score"), width="stretch")
    st.caption("เส้นน้ำเงิน = ราคาปิด  \nเส้นแดง = Sentiment Score (ผลรวม final_sentiment ÷ จำนวนข้อความของชั่วโมงนั้น) "
               "ช่วงที่เส้นแดงขาด = ไม่มีข้อความ ไม่ใช่ค่ากลาง")

# ---- does higher sentiment go with a higher return?  every ticked ticker-hour with text is one sample
st.subheader("ความรู้สึกยิ่งสูง ผลตอบแทนยิ่งสูงไหม")
MEASURES = {"Current Return (ชั่วโมงเดียวกัน)": "log_return", **{"ผลตอบแทนล่วงหน้า %s" % h: "future_return_" + h for h in common.data.HORIZONS}}
st.session_state.setdefault("s_bar_measure", "ผลตอบแทนล่วงหน้า 1h")
picked = st.radio("วัดผลตอบแทนแบบ", list(MEASURES), horizontal=True, key="s_bar_measure", label_visibility="collapsed")
column = MEASURES[picked]
returns = prices[["ticker", "hour_utc", "log_return", *["future_return_" + h for h in common.data.HORIZONS]]]
samples = per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]].merge(
    returns, on=["ticker", "hour_utc"])
samples = samples[samples.majority.isin(statuses)]
buckets = data.sentiment_buckets(samples, column)
if buckets.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มความรู้สึก (ต้องมีอย่างน้อย 50 ticker-ชั่วโมงที่มีทั้งข้อความและผลตอบแทน)")
else:
    levels = data.SENTIMENT_LEVELS
    buckets["ระดับความรู้สึก"] = [levels[int(b)][0] for b in buckets.bucket]
    buckets["ช่วงความรู้สึก"] = ["Sentiment Score " + levels[int(b)][1] for b in buckets.bucket]
    buckets["ป้าย"] = ["%s (%s)" % levels[int(b)] for b in buckets.bucket]
    order = list(buckets["ป้าย"])
    base = alt.Chart(buckets).encode(x=alt.X("ป้าย:N", sort=order, axis=alt.Axis(labelAngle=0, labelLimit=200), title="ระดับความรู้สึก (ช่วง Sentiment Score ของแต่ละกลุ่ม)"))
    bars = base.mark_bar(color="#1f77b4").encode(
        y=alt.Y("mean:Q", title="ผลตอบแทนเฉลี่ย (%)"),
        tooltip=["ระดับความรู้สึก", "ช่วงความรู้สึก", alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","),
                 alt.Tooltip("sent_mean:Q", title="Sentiment Score เฉลี่ย", format="+.3f"), alt.Tooltip("mean:Q", title="ผลตอบแทนเฉลี่ย (%)", format=".4f"), alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format=".4f"),
                 alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format=".4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    paired = samples[["sentiment_mean", column]].dropna()
    st.caption("วิธีอ่าน: เอาทุก ticker-ชั่วโมงที่มีข้อความ มาใส่ 5 ระดับตาม Sentiment Score ของชั่วโมงนั้น โดยใช้เกณฑ์ตายตัวของ proposal: ±0.05 = ขอบเป็นกลาง, ±0.30 = เกณฑ์ความรู้สึกชัดเจน  \n"
               "แท่ง = ผลตอบแทนเฉลี่ยของระดับนั้น (ระดับที่ไม่มีข้อมูลจะไม่มีแท่ง) เส้นดำ = ช่วงเชื่อมั่น 95%% ถ้าเส้นคลุมศูนย์ แปลว่าแยกจากศูนย์ไม่ได้  \n"
               "Spearman ρ ระหว่างความรู้สึกกับผลตอบแทน = %+.3f (%s ticker-ชั่วโมง)  \n"
               "ใช้ผลตอบแทนแทนระดับราคา เพราะระดับราคาขึ้นลงตามแนวโน้มระยะยาว เทียบกับความรู้สึกตรงๆ จะหลอกตา"
               % (paired.sentiment_mean.corr(paired[column], method="spearman"), "{:,}".format(len(paired))))

# ---- who moves first?  the same ticker-hours as above, now looking back as well as forward
st.subheader("ใครขยับก่อนกัน: ความรู้สึก หรือ ราคา")
timing = per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "sentiment_mean", "majority"]]
timing = timing[timing.majority.isin(statuses)].merge(prices[["ticker", "hour_utc", "log_return"]], on=["ticker", "hour_utc"], how="left")
lags = data.lag_correlation(timing)
if lags.rho.notna().sum() == 0:
    st.info("ตัวอย่างน้อยเกินไปสำหรับวัดความสัมพันธ์ข้ามเวลา")
else:
    lags["ช่วงเวลา"] = lags.lag.map(lambda k: "ชั่วโมงเดียวกัน" if k == 0 else ("ราคาก่อน %d ชม." % -k if k < 0 else "ราคาหลัง %d ชม." % k))
    lags["ฝั่ง"] = lags.lag.map(lambda k: "ราคาขยับก่อนข้อความ" if k < 0 else ("ชั่วโมงเดียวกัน" if k == 0 else "ราคาขยับหลังข้อความ"))
    base = alt.Chart(lags).encode(x=alt.X("lag:O", title="ผลตอบแทนของชั่วโมงที่ห่างจากชั่วโมงที่มีข้อความกี่ชั่วโมง (ลบ = ก่อนมีข้อความ, บวก = หลังมีข้อความ)",
                                          axis=alt.Axis(labelAngle=0)))
    bars = base.mark_bar().encode(
        y=alt.Y("rho:Q", title="Spearman ρ (ความรู้สึก vs ผลตอบแทน)"),
        color=alt.Color("ฝั่ง:N", scale=alt.Scale(domain=["ราคาขยับก่อนข้อความ", "ชั่วโมงเดียวกัน", "ราคาขยับหลังข้อความ"],
                                                  range=["#d62728", "#7f7f7f", "#1f77b4"]), legend=alt.Legend(orient="top", title=None)),
        tooltip=["ช่วงเวลา", alt.Tooltip("rho:Q", title="Spearman ρ", format="+.3f"), alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.3f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.3f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    st.caption("วิธีอ่าน: แต่ละแท่งคือความสัมพันธ์ระหว่าง Sentiment Score ของชั่วโมงที่มีข้อความ กับผลตอบแทนรายชั่วโมงที่ห่างไปกี่ชั่วโมง "
               "ถ้าราคาขยับก่อนแล้วคนค่อยโพสต์ แท่งสีแดง (ฝั่งซ้าย) จะสูงกว่าสีน้ำเงิน ถ้าความรู้สึกนำราคา แท่งสีน้ำเงิน (ฝั่งขวา) จะสูงกว่า "
               "เส้นดำ = ช่วงเชื่อมั่น 95% ถ้าคร่อมศูนย์ แปลว่าแยกจากไม่มีความสัมพันธ์ไม่ได้")

st.subheader("ราคาขึ้นหรือลงมาก่อน แล้วความรู้สึกเป็นอย่างไร")
PAST = {"1 ชั่วโมงก่อนหน้า": 1, "3 ชั่วโมงก่อนหน้า": 3, "6 ชั่วโมงก่อนหน้า": 6}
st.session_state.setdefault("s_past_hours", "3 ชั่วโมงก่อนหน้า")
past_pick = st.radio("ดูผลตอบแทน", list(PAST), horizontal=True, key="s_past_hours", label_visibility="collapsed")
timing = timing.assign(past=data.past_return(timing, PAST[past_pick]))
rb = data.return_buckets(timing, "past")
if rb.empty:
    st.info("ตัวอย่างน้อยเกินไปสำหรับแบ่งกลุ่มตามผลตอบแทนก่อนหน้า (ต้องมีอย่างน้อย 50 ticker-ชั่วโมงที่มีทั้งข้อความและราคาก่อนหน้า)")
else:
    price_levels = ["ตกแรงสุด", "ตกเล็กน้อย", "ทรงตัว", "ขึ้นเล็กน้อย", "ขึ้นแรงสุด"]
    rb["ระดับราคา"] = [price_levels[int(b)] if len(rb) == 5 else "กลุ่ม %d" % (int(b) + 1) for b in rb.bucket]
    rb["ป้าย"] = rb.apply(lambda r: "%s (%+.2f%% ถึง %+.2f%%)" % (r["ระดับราคา"], r.lo, r.hi), axis=1)
    base = alt.Chart(rb).encode(x=alt.X("ป้าย:N", sort=list(rb["ป้าย"]), axis=alt.Axis(labelAngle=0, labelLimit=200),
                                        title="ผลตอบแทนก่อนชั่วโมงที่มีข้อความ (แบ่ง 5 กลุ่มเท่าๆ กัน จากตกแรงสุดไปขึ้นแรงสุด)"))
    bars = base.mark_bar(color="#d62728").encode(
        y=alt.Y("mean:Q", title="Sentiment Score เฉลี่ย"),
        tooltip=["ระดับราคา", alt.Tooltip("mean_return:Q", title="ผลตอบแทนก่อนหน้าเฉลี่ย (%)", format="+.3f"),
                 alt.Tooltip("n:Q", title="จำนวนตัวอย่าง", format=","), alt.Tooltip("mean:Q", title="Sentiment Score เฉลี่ย", format="+.4f"),
                 alt.Tooltip("ci_lo:Q", title="ช่วงเชื่อมั่น 95% ล่าง", format="+.4f"), alt.Tooltip("ci_hi:Q", title="ช่วงเชื่อมั่น 95% บน", format="+.4f")])
    errors = base.mark_rule(color="#222222", strokeWidth=2).encode(y="ci_lo:Q", y2="ci_hi:Q")
    zero = alt.Chart(alt.Data(values=[{"y": 0}])).mark_rule(color="#555555").encode(y="y:Q")
    st.altair_chart(bars + errors + zero, width="stretch")
    st.caption("วิธีอ่าน: แบ่ง ticker-ชั่วโมงที่มีข้อความเป็น 5 กลุ่มเท่าๆ กันตามผลตอบแทนของราคาก่อนชั่วโมงนั้น แล้วดู Sentiment Score เฉลี่ยของแต่ละกลุ่ม "
               "ถ้า \"ราคาตก คนก็กลัว\" แท่งซ้าย (ตกแรงสุด) ควรต่ำกว่าแท่งขวา (ขึ้นแรงสุด) เส้นดำ = ช่วงเชื่อมั่น 95%")

st.subheader("สัดส่วนความคิดเห็นเชิงบวก / ลบ / เป็นกลาง")
RATIO_MODES = ("ความคิดเห็นจริง (สัดส่วนข้อความ)", "ผลโหวตส่วนใหญ่ (สัดส่วนชั่วโมง)")
mode = st.radio("นับสัดส่วนจาก", RATIO_MODES, horizontal=True, key="s_ratio_mode", label_visibility="collapsed")
COLORS = alt.Scale(domain=["บวก", "ลบ", "เป็นกลาง"], range=["#2ca02c", "#d62728", "#7f7f7f"])
if mode == RATIO_MODES[0]:
    ratios = shown.melt(id_vars="time", value_vars=["pos_ratio", "neg_ratio", "neu_ratio"], var_name="ประเภท",
                        value_name="สัดส่วน").dropna()
    ratios["ประเภท"] = ratios["ประเภท"].map({"pos_ratio": "บวก", "neg_ratio": "ลบ", "neu_ratio": "เป็นกลาง"})
    caption = ("สัดส่วนของข้อความ บวก / ลบ / เป็นกลาง ภายในชั่วโมงที่ผ่านตัวกรอง (ค่าจริงของ pos_ratio, neg_ratio, neu_ratio) "
               "ชั่วโมงที่ส่วนใหญ่เป็นประเภทที่ติ๊กออกไม่ถูกนับ แต่ชั่วโมงที่เหลือยังมีข้อความประเภทนั้นปนอยู่")
else:
    votes = data.vote_shares(series, None if how == "Hourly" else common.RESAMPLE[how])
    ratios = votes.rename(columns={"share": "สัดส่วน"}).assign(ประเภท=lambda d: d.status.map(
        {"positive": "บวก", "negative": "ลบ", "neutral": "เป็นกลาง"}))
    caption = ("สัดส่วนของ**ชั่วโมง**ที่ผลโหวตส่วนใหญ่เป็น บวก / ลบ / เป็นกลาง (นับ 1 ชั่วโมง = 1 โหวต) "
               "ประเภทที่ติ๊กออกจะเป็น 0 ทั้งหมด")
if not ratios.empty:
    area = (alt.Chart(ratios).mark_area().encode(
        x=alt.X("time:T", title=None), y=alt.Y("สัดส่วน:Q", stack="normalize", axis=alt.Axis(format="%")),
        color=alt.Color("ประเภท:N", scale=COLORS), tooltip=["time:T", "ประเภท", alt.Tooltip("สัดส่วน:Q", format=".1%")])
        .properties(height=240))
    st.altair_chart(area, width="stretch")
    st.caption(caption)

st.subheader("ประเภทความรู้สึกส่วนใหญ่ (จำนวนชั่วโมง)")
maj = series.majority_final_status.value_counts().rename_axis("ประเภท").reset_index(name="ชั่วโมง")
common.table(maj, hide_index=True, width="stretch")

st.subheader("ประเภทความรู้สึกส่วนใหญ่ สอดคล้องกับทิศทางผลตอบแทนอนาคตหรือไม่")
# every ticked ticker-hour is one sample: its majority status (chosen communities) against ITS future returns
samples = prices.merge(per_ticker.rename(columns={"series": "ticker"})[["ticker", "hour_utc", "majority"]], on=["ticker", "hour_utc"])
samples = samples[samples.majority.isin(statuses)]
rows = []
for h in common.data.HORIZONS:
    col = "future_return_" + h
    for status, part in samples.groupby("majority"):
        moved = part[col].dropna()
        rows.append({"majority": status, "horizon": h, "n": len(moved),
                     "share_up": float((moved > 0).sum() / ((moved > 0).sum() + (moved < 0).sum())) if ((moved != 0).sum()) else np.nan})
mv = pd.DataFrame(rows)
if mv.empty:
    st.info("ไม่มีข้อมูลเพียงพอ")
else:
    table = mv.pivot(index="majority", columns="horizon", values="share_up").reindex(columns=list(common.data.HORIZONS))
    counts = mv.pivot(index="majority", columns="horizon", values="n").reindex(columns=list(common.data.HORIZONS))
    st.write("สัดส่วนชั่วโมงที่ผลตอบแทนอนาคตเป็นบวก (แยกตามประเภทความรู้สึกส่วนใหญ่)")
    st.dataframe((table * 100).map(lambda v: "n/a" if pd.isna(v) else "%.1f" % v), width="stretch")
    st.caption("ถ้าความรู้สึกบวกนำราคา แถว positive ควรสูงกว่าแถว negative  \nจำนวนตัวอย่างต่อช่อง: "
               + ", ".join("%s/%s=%s" % (i, c, "{:,}".format(int(counts.loc[i, c]))) for i in counts.index
                           for c in counts.columns if pd.notna(counts.loc[i, c]))[:400])

st.subheader("สินทรัพย์ใดมีความรู้สึกเชิงบวก/ลบมากที่สุดในช่วงนี้")
hours = prices[["ticker", "hour_utc"]]
by_ticker = per_ticker.rename(columns={"series": "ticker"}).merge(hours, on=["ticker", "hour_utc"])
by_ticker = by_ticker[by_ticker.majority.isin(statuses) & by_ticker.sentiment_mean.notna()]
if by_ticker.empty:
    st.info("ไม่มีข้อความตามตัวกรองที่เลือก")
else:
    rank = by_ticker.groupby("ticker").agg(mean_sentiment=("sentiment_mean", "mean"), pos_ratio=("pos_ratio", "mean"),
                                           neg_ratio=("neg_ratio", "mean"), hours_with_text=("sentiment_mean", "size"),
                                           texts=("texts", "sum")).reset_index().sort_values("mean_sentiment", ascending=False)
    rank["สินทรัพย์"] = rank.ticker.map(lambda s: "%s · %s" % (s, names.get(s, "")))
    rank["กลุ่ม"] = rank.ticker.map(dict(zip(q("tickers").ticker, q("tickers").big_group))).map(GROUP_LABELS)
    common.table(rank[["สินทรัพย์", "กลุ่ม", "mean_sentiment", "pos_ratio", "neg_ratio", "hours_with_text", "texts"]].rename(
        columns={"mean_sentiment": "Sentiment Score เฉลี่ย", "pos_ratio": "สัดส่วนบวก", "neg_ratio": "สัดส่วนลบ",
                 "hours_with_text": "ชั่วโมงที่มีข้อความ", "texts": "ข้อความ"}).round(3), hide_index=True,
        width="stretch", height=330)

# ---- below: the market measures (close, volume) do not depend on the sentiment filters (communities, majority status)
st.subheader("ราคาปิดและปริมาณการซื้อขาย (ไม่ขึ้นกับตัวกรองความรู้สึก)")
st.altair_chart(common.line(shown, "time", "close", "ราคาปิด (USD)" if one else "ราคาปิด ดัชนี (ค่าแรก = 100)", "#1f77b4", 220,
                            bar=common.kind(st, "s_price")), width="stretch")
st.altair_chart(common.line(shown, "time", "volume", "ปริมาณซื้อขาย (หน่วย)" if one else "ปริมาณซื้อขาย ดัชนี (ค่าเฉลี่ย = 100)",
                            "#2ca02c", 220, bar=common.kind(st, "s_market_volume")), width="stretch")
