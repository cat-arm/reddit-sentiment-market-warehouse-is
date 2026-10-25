"""Shared look of the A1/A2 heatmaps: red = below the reference value, green = above it, Thai captions, n in every cell."""

import numpy as np

THAI_FONTS = ["Leelawadee UI", "Tahoma", "TH Sarabun New", "DejaVu Sans"]
RED_GREEN = ["#b2182b", "#f4f4f4", "#1a9850"]            # dark red (low) - near white (reference) - dark green (high)

SCOPE_NOTE = {"panel_global": "ความรู้สึกรวมของทั้ง Reddit (ทุกข้อความในชั่วโมงนั้น)",
              "panel_Ticker": "ความรู้สึกเฉพาะข้อความที่พูดถึงสินทรัพย์นั้น"}
FILTER_NOTE = {"": "ใช้ทุกข้อความ",
               "strong": "เฉพาะข้อความที่ |คะแนน| ≥ 0.05",
               "quality": "เฉพาะข้อความที่ |คะแนน| ≥ 0.30 (ชัดมาก)",
               "spike": "เฉพาะชั่วโมงที่ปริมาณโพสต์พุ่งผิดปกติ (z > 1.5 เทียบ 24 ชั่วโมงก่อนหน้า)"}


def use_thai_font():
    import matplotlib
    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = THAI_FONTS
    matplotlib.rcParams["axes.unicode_minus"] = False


def colormap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("red_white_green", RED_GREEN)


def panel_note(panel_name):
    """One short Thai line saying what rows the panel holds, e.g. quality = |score| >= 0.30."""
    if panel_name == "panel_baseline":
        return "ทิศทางสุ่ม (ตัวควบคุม ไม่ใช้ความรู้สึก) บนแถวชุดเดียวกับ panel_global"
    scope = "panel_Ticker" if panel_name.startswith("panel_Ticker") else "panel_global"
    kind = panel_name.split("_")[-1] if panel_name not in SCOPE_NOTE else ""
    return "%s; %s" % (SCOPE_NOTE[scope], FILTER_NOTE.get(kind, ""))


def cell_labels(values, counts, p_adjusted, value_text):
    """'value*' + newline + 'n=count' for every cell; '*' = Benjamini-Hochberg p < 0.05; 'n/a' where nothing was computed."""
    rows = []
    for vrow, nrow, prow in zip(values, counts, p_adjusted):
        row = []
        for v, n, p in zip(vrow, nrow, prow):
            if np.isnan(v):
                row.append("n/a\nn=%s" % ("0" if np.isnan(n) else "{:,}".format(int(n))))
            else:
                row.append("%s%s\nn=%s" % (value_text(v), "*" if p < 0.05 else "", "{:,}".format(int(n))))
        rows.append(row)
    return np.array(rows, dtype=object)
