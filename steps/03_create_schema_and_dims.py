"""Step 03: สร้างตาราง star schema (db/schema.sql) และเติม Dim ทั้ง 6

Run:  python steps/03_create_schema_and_dims.py 
"""

from _run import module

module("etl.seed_dims")
