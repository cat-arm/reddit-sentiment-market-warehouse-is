"""S5: sentiment QA report from `sentiment_item` -> table `sentiment_qa` (+ printed).

    sentiment_qa(section, label, n, share)
      model_status       share of positive/negative/neutral per model and for final_status
      model_agreement    VADER vs FinBERT: same_direction / both_neutral / small_conflict / hard_conflict
      final_method       how final_sentiment was produced
      is_ambiguous       texts whose final 0.0 comes from an undecidable conflict (proposal Table 11)
      rule_signal        keyword signal distribution
      range_check        rows with a missing method or final_sentiment outside [-1, 1] (must be 0)
Answers the management question "how consistent are VADER and FinBERT and how are conflicts resolved".
The table is rebuilt on every run.

Usage:  python -m etl.sentiment_qa [--db output/reddit.sqlite3]
"""

import argparse
import sys

from etl.common import DEFAULT_DB, connect

AGREEMENT = ("CASE WHEN vader_status = finbert_status THEN "
             "CASE vader_status WHEN 'neutral' THEN 'both_neutral' ELSE 'same_direction' END "
             "WHEN vader_status = 'neutral' OR finbert_status = 'neutral' THEN 'small_conflict' "
             "ELSE 'hard_conflict' END")


def build(db_path=DEFAULT_DB):
    db = connect(db_path)
    try:
        db.execute("DROP TABLE IF EXISTS sentiment_qa")
        db.execute("CREATE TABLE sentiment_qa (section TEXT, label TEXT, n INTEGER, share REAL)")
        total = db.execute("SELECT COUNT(*) FROM sentiment_item").fetchone()[0]
        queries = {
            "model_status": " UNION ALL ".join(
                "SELECT '%s=' || %s, COUNT(*) FROM sentiment_item GROUP BY 1" % (m, c)
                for m, c in (("vader", "vader_status"), ("finbert", "finbert_status"), ("final", "final_status")))
            .replace("GROUP BY 1 UNION", "GROUP BY 1 UNION"),
            "model_agreement": "SELECT %s, COUNT(*) FROM sentiment_item "
                               "WHERE vader_status IS NOT NULL AND finbert_status IS NOT NULL GROUP BY 1" % AGREEMENT,
            "final_method": "SELECT final_method, COUNT(*) FROM sentiment_item GROUP BY 1",
            "is_ambiguous": "SELECT 'is_ambiguous=' || is_ambiguous, COUNT(*) FROM sentiment_item GROUP BY 1",
            "rule_signal": "SELECT rule_signal, COUNT(*) FROM sentiment_item GROUP BY 1",
            "range_check": "SELECT 'bad_rows', COUNT(*) FROM sentiment_item WHERE final_method = '' "
                           "OR final_sentiment < -1 OR final_sentiment > 1 OR final_sentiment IS NULL",
        }
        for section, sql in queries.items():
            for label, n in db.execute(sql).fetchall():
                db.execute("INSERT INTO sentiment_qa VALUES (?,?,?,?)", (section, label, n, n / total))
        db.commit()
        rows = db.execute("SELECT section, label, n, share FROM sentiment_qa ORDER BY section, n DESC").fetchall()
        print("total texts: %d" % total)
        for section, label, n, share in rows:
            print("%-16s %-28s %12d  %6.2f%%" % (section, label, n, share * 100))
        return rows
    finally:
        db.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=str(DEFAULT_DB))
    build(parser.parse_args(argv).db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
