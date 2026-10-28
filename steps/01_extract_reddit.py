"""Step 01: ดึง/นำเข้าข้อมูล Reddit ดิบ -> reddit_content

Run:  python steps/01_extract_reddit.py fetch 2026-03 --db output/reddit.sqlite3
"""

from _run import script

script("ingest/reddit_extract.py")
