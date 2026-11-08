"""Charts and numbers of the System 1 and System 3 slides of the defence deck, drawn as PNG pictures (native PowerPoint charts do not
show in Keynote).  Numbers come from the 400-label rule validation (output/reports/rule_validation/), the dashboard data functions
and the figures the book gives for the whole data set.

Usage:  python scripts/deck_charts.py [--db output/reddit.sqlite3]
Output: output/figures/deck/*.png  and  output/reports/deck_rule_test.json  (read by docs/presentation/build_deck_en.js)
Run first:  python steps/26_rule_validation.py evaluate  and  python steps/29_rule_validation_extras.py
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib                                      # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt                        # noqa: E402

from dashboard import data                             # noqa: E402
from etl.common import DEFAULT_DB                      # noqa: E402

RV = ROOT / "output" / "reports" / "rule_validation"
FIG = ROOT / "output" / "figures" / "deck"
OUT_JSON = ROOT / "output" / "reports" / "deck_rule_test.json"
BG, SURF, EDGE, INK, SOFT, MUTE = "#0A1020", "#141F3A", "#26355A", "#F4F7FC", "#C3CFE4", "#8392B0"
TEAL, AMBER, CORAL, BLUE, GREEN = "#2DD4BF", "#F5B942", "#FF7A70", "#6AA6FF", "#3DDC97"
GROUPS = ["same_direction", "same_direction_far", "both_neutral", "small_conflict_keyword", "small_conflict_no_keyword",
          "hard_conflict_keyword", "hard_conflict_no_keyword"]
GROUP_LABEL = {"same_direction": "Same\ndirection", "same_direction_far": "Same, far\napart", "both_neutral": "Both\nneutral",
               "small_conflict_keyword": "One neutral,\nkeyword", "small_conflict_no_keyword": "One neutral,\nno keyword",
               "hard_conflict_keyword": "Opposite,\nkeyword", "hard_conflict_no_keyword": "Opposite,\nno keyword"}


def style(w, h):
    plt.rcParams.update({"font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"], "text.color": INK, "axes.labelcolor": SOFT,
                         "xtick.color": SOFT, "ytick.color": MUTE})
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(EDGE)
    ax.tick_params(length=0)
    return fig, ax


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, facecolor=BG, bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)


def grouped(ax, labels, series, colors, ymax, fmt="%.1f", width=0.8):
    n = len(series)
    w = width / n
    for i, (name, vals) in enumerate(series):
        xs = [k - width / 2 + w * (i + 0.5) for k in range(len(labels))]
        bars = ax.bar(xs, vals, w * 0.92, color=colors[i], label=name)
        for x, v, b in zip(xs, vals, bars):
            ax.text(x, v + ymax * 0.015, fmt % v, ha="center", va="bottom", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(0, ymax)
    ax.set_yticks([])
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=n, frameon=False, labelcolor=SOFT, fontsize=10)


def parse_md():
    text = (RV / "rule_validation.md").read_text(encoding="utf-8")
    variants = {}
    for m in re.finditer(r"^\| (A|B|C|cascade) \| (tune|test|รวม) \| (\d+) \| (–|[\d.]+%) \| (–|[\d.]+%) \| ([\d.]+)% \|$", text, re.M):
        f = lambda v: None if v == "–" else float(v.rstrip("%"))
        variants.setdefault(m.group(1), {})[m.group(2)] = {"n": int(m.group(3)), "vader": f(m.group(4)), "finbert": f(m.group(5)), "final": float(m.group(6))}
    paired = {}
    for m in re.finditer(r"^\| (A|C|cascade) \| (tune|test|รวม) \| (\d+) \| (\d+) \| (\d+) \| ([\d.]+) \|$", text, re.M):
        paired.setdefault(m.group(1), {})[m.group(2)] = {"n": int(m.group(3)), "only_variant": int(m.group(4)), "only_b": int(m.group(5)), "p": float(m.group(6))}
    band = {}
    for m in re.finditer(r"^\| ทั้งหมด \| (VADER|FinBERT|รวมผล \(final\)) \| ([\d.]+)% \| ([\d.]+)% \| ([+-][\d.]+) \|$",
                         (RV / "band_and_confusion.md").read_text(encoding="utf-8"), re.M):
        band[m.group(1).split(" ")[0]] = {"b05": float(m.group(2)), "b10": float(m.group(3))}
    return variants, paired, band


def insight_charts():
    """The four insight stories (numbers from scripts/deck_insights.py -> output/reports/insight_stories.json)."""
    import numpy as np
    d = json.loads((ROOT / "output" / "reports" / "insight_stories.json").read_text(encoding="utf-8"))
    # story 1: all hours against busy hours
    rows = [r for r in d["story1"] if r["spike"]["bh"] < 0.05 and r["spike"]["rho"] > 0]
    fig, ax = style(7.4, 4.6)
    grouped(ax, [r["ticker"] for r in rows], [("All hours", [r["all"]["rho"] for r in rows]), ("Busy hours (Z > 1.5)", [r["spike"]["rho"] for r in rows])],
            [MUTE, TEAL], 0.23, fmt="%.2f")
    ax.set_xticklabels([r["ticker"] for r in rows], fontsize=8.5, rotation=30)
    ax.set_title("Same-hour Spearman correlation: market-wide sentiment vs Current Return", color=INK, fontsize=11, loc="left")
    save(fig, "story1.png")
    # story 2: who moves first, ES=F in busy hours
    lag = d["story2"]["ES=F"]
    fig, ax = style(7.4, 4.6)
    xs = [x["lag"] for x in lag]
    cols = [CORAL if x < 0 else (MUTE if x == 0 else BLUE) for x in xs]
    bars = ax.bar(xs, [x["rho"] for x in lag], color=cols, width=0.7)
    for x, b in zip(lag, bars):
        ax.text(b.get_x() + b.get_width() / 2, x["rho"] + (0.008 if x["rho"] >= 0 else -0.02), "%.2f" % x["rho"], ha="center", fontsize=9, color=INK)
    ax.axhline(0, color=EDGE, lw=1)
    ax.set_xticks(xs); ax.set_yticks([]); ax.set_xlabel("Hours between the Reddit hour and the return (negative = price moved first)", fontsize=10)
    ax.set_title("ES=F, busy hours: correlation with the return k hours away", color=INK, fontsize=11, loc="left")
    save(fig, "story2.png")
    # story 3: the busiest hour
    win = d["story3_window"]
    hours = [w["hour"][11:16] for w in win]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.4, 4.8), dpi=200, gridspec_kw={"height_ratios": [1, 1.25], "hspace": 0.45})
    fig.patch.set_facecolor(BG)
    for a in (a1, a2):
        a.set_facecolor(BG)
        for side in ("top", "right", "left"):
            a.spines[side].set_visible(False)
        a.spines["bottom"].set_color(EDGE); a.tick_params(length=0); a.set_yticks([]); a.tick_params(axis="x", colors=SOFT, labelsize=9)
    texts = [w["texts"] for w in win]
    bars = a1.bar(hours, texts, color=[AMBER if t == max(texts) else "#52618A" for t in texts], width=0.65)
    for b, w in zip(bars, win):
        a1.text(b.get_x() + b.get_width() / 2, w["texts"] + 300, "{:,}".format(w["texts"]), ha="center", fontsize=8, color=INK)
    a1.set_ylim(0, 21000)
    a1.set_xticks(range(len(win))); a1.set_xticklabels(["%s\nmood %+.3f" % (h, w["sentiment"]) for h, w in zip(hours, win)], fontsize=8)
    a1.set_title("Reddit texts per hour (UTC, 9 Apr 2025) and market-wide mood", color=INK, fontsize=10.5, loc="left")
    names = [("ES=F", BLUE), ("BTC-USD", AMBER), ("TSLA", CORAL)]
    wdt = 0.26
    for i, (t, c) in enumerate(names):
        vals = [w["ret_" + t] for w in win]
        xs = [k - wdt + i * wdt for k in range(len(win))]
        ys = [v if v is not None else 0 for v in vals]
        a2.bar(xs, ys, wdt * 0.92, color=c, label=t)
        for x, v in zip(xs, vals):
            if v is not None and abs(v) >= 3:
                a2.text(x, v + 0.25, "%.1f" % v, ha="center", fontsize=7.5, color=INK)
    a2.set_xticks(range(len(win))); a2.set_xticklabels(hours)
    a2.axhline(0, color=EDGE, lw=1)
    a2.set_ylim(-2.5, 11.5)
    a2.legend(loc="upper left", frameon=False, ncol=3, labelcolor=SOFT, fontsize=9)
    a2.set_title("Return in that hour (%)", color=INK, fontsize=10.5, loc="left")
    save(fig, "story3.png")
    # story 4: significant but tiny win rates
    items = d["story4"]
    fig, ax = style(7.4, 4.6)
    ys = list(range(len(items)))[::-1]
    for y, it in zip(ys, items):
        ax.plot([50, it["win_rate"]], [y, y], color=EDGE, lw=2)
        ax.scatter([it["win_rate"]], [y], s=90, color=TEAL if it["win_rate"] > 50 else CORAL, zorder=3)
        ax.text(it["win_rate"] + (0.25 if it["win_rate"] >= 50 else -0.25), y, "%.1f%%" % it["win_rate"], va="center", ha="left" if it["win_rate"] >= 50 else "right", fontsize=9, color=INK)
    ax.axvline(50, color=MUTE, lw=1, ls="--")
    ax.set_yticks(ys); ax.set_yticklabels(["%s  %s  (n=%s)" % (i["ticker"], i["horizon"], "{:,}".format(i["n"])) for i in items], fontsize=9.5)
    ax.set_xlim(42, 54); ax.set_xlabel("Win rate (%), dashed line = coin flip", fontsize=10)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", colors=SOFT)
    ax.set_title("Win rates that pass the Benjamini-Hochberg test", color=INK, fontsize=11, loc="left")
    save(fig, "story4.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    db = parser.parse_args(argv).db
    variants, paired, band = parse_md()

    # per rule group: accuracy over tune + test, and the share the labeller called neutral (= "always neutral")
    counts = {g: {"n": 0, "vader": 0, "finbert": 0, "final": 0} for g in GROUPS}
    with open(RV / "rule_validation.csv", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith("#")]
    for r in rows[1:]:
        c = counts[r[0]]
        c["n"] += int(r[2]); c["vader"] += int(r[3]); c["finbert"] += int(r[4]); c["final"] += int(r[5])
    labels = {}
    with open(RV / "labeling_sheet.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            labels[r["sample_id"]] = r["human_label"].strip().lower()
    pop, neutral = {}, {g: [0, 0] for g in GROUPS}
    with open(RV / "sample_key.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            pop[r["stratum"]] = int(r["stratum_population"])
            if r["stratum"] in neutral and labels.get(r["sample_id"]):
                neutral[r["stratum"]][1] += 1
                neutral[r["stratum"]][0] += labels[r["sample_id"]] == "neutral"
    pct = lambda a, b: 100.0 * a / b
    per_group = {g: {"n": counts[g]["n"], "population": pop[g], "vader": pct(counts[g]["vader"], counts[g]["n"]),
                     "finbert": pct(counts[g]["finbert"], counts[g]["n"]), "final": pct(counts[g]["final"], counts[g]["n"]),
                     "always_neutral": pct(*neutral[g])} for g in GROUPS}

    # 1 communities (System 1)
    inv = data.reddit_inventory(db)
    inv["total"] = inv.posts + inv.comments
    fig, ax = style(7.0, 4.6)
    names = ["r/" + s.split("/")[-1] for s in inv.subreddit][::-1]
    vals = list(inv.total)[::-1]
    bars = ax.barh(names, vals, color=TEAL, height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + max(vals) * 0.015, b.get_y() + b.get_height() / 2, "{:,}".format(int(v)), va="center", fontsize=10, color=INK)
    ax.set_xlim(0, max(vals) * 1.28); ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="y", labelsize=11)
    ax.set_title("Texts per community (cleaned, scored)", color=INK, fontsize=12, loc="left")
    save(fig, "communities.png")

    # 2 agreement doughnut
    fig, ax = plt.subplots(figsize=(6.0, 4.6), dpi=200)
    fig.patch.set_facecolor(BG)
    parts = [50.15, 37.59, 12.26]
    wedges, _ = ax.pie(parts, colors=[GREEN, AMBER, CORAL], startangle=90, counterclock=False, wedgeprops={"width": 0.42, "edgecolor": BG, "linewidth": 3})
    for w_, v in zip(wedges, parts):
        ang = (w_.theta2 + w_.theta1) / 2
        import numpy as np
        ax.text(0.79 * np.cos(np.deg2rad(ang)), 0.79 * np.sin(np.deg2rad(ang)), "%.2f%%" % v, ha="center", va="center", fontsize=11, color=BG, fontweight="bold")
    ax.legend(wedges, ["Same direction", "One neutral, one directional", "Opposite directions"], loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=1, frameon=False, labelcolor=SOFT, fontsize=10.5)
    save(fig, "agreement.png")

    # 3 final shares
    fig, ax = style(7.6, 4.6)
    grouped(ax, ["Positive", "Neutral", "Negative"], [("VADER", [38.81, 30.27, 30.92]), ("FinBERT", [17.25, 48.41, 34.35]), ("Final sentiment", [32.41, 32.86, 34.72])],
            [MUTE, BLUE, TEAL], 58)
    ax.set_title("Share of texts by class (%), neutral band ±0.05", color=INK, fontsize=12, loc="left")
    save(fig, "final_shares.png")

    # 4 per rule group (400 labels)
    fig, ax = style(12.1, 4.3)
    grouped(ax, [GROUP_LABEL[g] for g in GROUPS], [("VADER alone", [per_group[g]["vader"] for g in GROUPS]), ("FinBERT alone", [per_group[g]["finbert"] for g in GROUPS]),
            ("Merge rule", [per_group[g]["final"] for g in GROUPS]), ("Always neutral", [per_group[g]["always_neutral"] for g in GROUPS])],
            [MUTE, BLUE, TEAL, "#52618A"], 82, fmt="%.0f", width=0.84)
    save(fig, "per_rule_group.png")

    # 5 overall accuracy (400 labels, text variant B)
    fig, ax = style(6.6, 4.2)
    b = variants["B"]
    grouped(ax, ["Tune half", "Test half", "All 400"], [("VADER alone", [b["tune"]["vader"], b["test"]["vader"], b["รวม"]["vader"]]),
            ("FinBERT alone", [b["tune"]["finbert"], b["test"]["finbert"], b["รวม"]["finbert"]]), ("Merge rule", [b["tune"]["final"], b["test"]["final"], b["รวม"]["final"]])],
            [MUTE, BLUE, TEAL], 62)
    ax.set_title("Accuracy against hand labels (%)", color=INK, fontsize=12, loc="left")
    save(fig, "overall_accuracy.png")

    # 6 text variants
    fig, ax = style(6.6, 4.2)
    names6 = ["A  comment only", "B  title +\ncomment (used)", "C  + post body", "Cascade\nA → B → C"]
    vals6 = [variants["A"]["รวม"]["final"], variants["B"]["รวม"]["final"], variants["C"]["รวม"]["final"], variants["cascade"]["รวม"]["final"]]
    bars = ax.bar(names6, vals6, color=[BLUE, TEAL, CORAL, CORAL], width=0.62)
    for bar, v in zip(bars, vals6):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1, "%.1f" % v, ha="center", fontsize=11, color=INK)
    ax.set_ylim(0, 60); ax.set_yticks([]); ax.tick_params(axis="x", labelsize=10)
    ax.set_title("Merge-rule accuracy by text sent to the models (%)", color=INK, fontsize=12, loc="left")
    save(fig, "text_variants.png")

    insight_charts()

    OUT_JSON.write_text(json.dumps({"variants": variants, "paired_vs_B": paired, "band": band, "per_group": per_group,
                                    "labels": {k: sum(1 for v in labels.values() if v == k) for k in ("positive", "negative", "neutral")}},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"variants": variants, "paired": paired, "band": band}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
