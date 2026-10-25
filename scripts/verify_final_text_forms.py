"""Prove that final_text has only two forms: post title + post body, and post title + comment body.

Re-derives every row of processed_text from the raw reddit_content table with the cleaner's own functions and
counts the rows that do not match.  Submissions must equal clean(title + selftext); comments must equal
clean(parent post title) + " " + clean(comment body), or just clean(comment body) when the parent post is not in
the database.  Read-only.

Usage:  python scripts/verify_final_text_forms.py [--db output/reddit.sqlite3]
Output: output/reports/final_text_forms.md
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.clean_text import build_texts, post_titles  # noqa: E402
from etl.common import DEFAULT_DB, connect, file_header, subreddits  # noqa: E402

OUT = ROOT / "output" / "reports" / "final_text_forms.md"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    db = connect(args.db, readonly=True)
    names = subreddits()
    counts = Counter()
    bad = []
    try:
        titles = post_titles(db, names)
        marks = ",".join("?" * len(names))
        cursor = db.execute(
            "SELECT p.content_type, p.final_text, p.own_text, r.title, r.selftext, r.body, r.link_id, p.content_id "
            "FROM processed_text p JOIN reddit_content r ON r.rowid = p.src_rowid WHERE p.subreddit IN (%s)" % marks, names)
        for ctype, final, own, title, selftext, body, link_id, content_id in cursor:
            parent = titles.get(link_id, "") if ctype == "comment" else ""
            expected_final, expected_own = build_texts(ctype, title, selftext, body, parent)
            form = ("submission: title + body" if ctype != "comment"
                    else "comment: post title + comment body" if parent else "comment: comment body only (parent post not in DB)")
            counts[form] += 1
            if final != expected_final or own != expected_own:
                counts[form + " | MISMATCH"] += 1
                if len(bad) < 5:
                    bad.append((content_id, ctype))
    finally:
        db.close()
    lines = ["# final_text มีกี่รูปแบบ — ตรวจทุกแถวของ processed_text", "",
             *file_header("พิสูจน์ว่า final_text มีแค่ 2 รูปแบบ: (โพสต์) title + body และ (คอมเมนต์) title ของโพสต์แม่ + body คอมเมนต์ "
                          "โดยสร้างข้อความขึ้นใหม่จากตารางดิบทุกแถวด้วยฟังก์ชันของตัวล้างข้อความ แล้วนับแถวที่ไม่ตรง",
                          "scripts/verify_final_text_forms.py", "python scripts/verify_final_text_forms.py",
                          "processed_text เทียบ reddit_content และ title ของโพสต์แม่ (เฉพาะ 6 ชุมชน) อ่านอย่างเดียว"), "",
             "| รูปแบบ | จำนวนแถว | แถวที่ไม่ตรง |", "|---|---|---|"]
    for form in sorted(f for f in counts if "MISMATCH" not in f):
        lines.append("| %s | %d | %d |" % (form, counts[form], counts[form + " | MISMATCH"]))
    if bad:
        lines += ["", "ตัวอย่างแถวที่ไม่ตรง: " + ", ".join("%s (%s)" % b for b in bad)]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
