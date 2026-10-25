import csv
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rule_validation = load("rule_validation")
band = load("neutral_band_sensitivity")


def make_db(path):
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE sentiment_item (src_rowid INTEGER PRIMARY KEY, vader_score REAL, vader_status TEXT,"
               " finbert_score REAL, finbert_status TEXT, rule_signal TEXT, final_sentiment REAL, final_status TEXT,"
               " final_method TEXT, is_ambiguous INTEGER)")
    db.execute("CREATE TABLE filtered_text (src_rowid INTEGER PRIMARY KEY, final_text TEXT, char_len INTEGER)")
    rowid = 0
    for methods in rule_validation.STRATA.values():
        for k in range(8):
            rowid += 1
            db.execute("INSERT INTO sentiment_item VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (rowid, 0.6, "positive", 0.4, "positive", "none", 0.5, "positive", methods[0], 0))
            db.execute("INSERT INTO filtered_text VALUES (?,?,?)", (rowid, "text number %d" % rowid, 30))
    db.execute("INSERT INTO filtered_text VALUES (999, 'too long', 5000)")       # filtered out by --max-chars
    db.execute("INSERT INTO sentiment_item VALUES (999,0.6,'positive',0.4,'positive','none',0.5,'positive',"
               "'same_direction',0)")
    db.commit()
    db.close()


class RuleValidationTests(unittest.TestCase):
    def test_sample_then_evaluate(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
            folder = Path(folder)
            make_db(folder / "t.sqlite3")
            out = folder / "out"
            args = ["sample", "--db", str(folder / "t.sqlite3"), "--per-stratum", "4", "--max-chars", "600",
                    "--out-dir", str(out)]
            self.assertEqual(rule_validation.main(args), 0)
            with (out / "labeling_sheet.csv").open(newline="", encoding="utf-8-sig") as handle:
                sheet = list(csv.DictReader(handle))
            self.assertEqual(len(sheet), 4 * len(rule_validation.STRATA))
            self.assertEqual(set(sheet[0]), {"sample_id", "final_text", "human_label"})   # no scores in the sheet
            self.assertNotIn("too long", [row["final_text"] for row in sheet])
            with self.assertRaises(SystemExit):                                          # never overwrite labels
                rule_validation.main(args)
            with (out / "sample_key.csv").open(newline="", encoding="utf-8") as handle:
                key = list(csv.DictReader(handle))
            for stratum in rule_validation.STRATA:
                splits = sorted(row["split"] for row in key if row["stratum"] == stratum)
                self.assertEqual(splits, ["test", "test", "tune", "tune"])
            for row in sheet:                                                            # label everything positive
                row["human_label"] = "Positive"
            with (out / "labeling_sheet.csv").open("w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(sheet[0]))
                writer.writeheader()
                writer.writerows(sheet)
            self.assertEqual(rule_validation.main(["evaluate", "--out-dir", str(out)]), 0)
            self.assertIn("same_direction_far", (out / "rule_validation.md").read_text(encoding="utf-8"))

    def test_accuracy_counts_and_weighting(self):
        def row(split, stratum, population, vader, finbert, final):
            return ({"split": split, "stratum": stratum, "stratum_population": population, "vader_status": vader,
                     "finbert_status": finbert, "final_status": final})
        labelled = [(row("test", "a", 100, "positive", "negative", "positive"), "positive"),
                    (row("test", "a", 100, "negative", "negative", "negative"), "positive"),
                    (row("test", "b", 300, "neutral", "neutral", "neutral"), "neutral")]
        table = rule_validation.accuracy_table(labelled)
        self.assertEqual(table[("a", "test")], {"n": 2, "vader": 1, "finbert": 0, "final": 1})
        overall = rule_validation.weighted_overall(labelled, "test")
        self.assertAlmostEqual(overall["final"], (100 * 0.5 + 300 * 1.0) / 400)
        self.assertAlmostEqual(overall["finbert"], (100 * 0.0 + 300 * 1.0) / 400)
        self.assertIsNone(rule_validation.weighted_overall(labelled, "tune"))

    def test_label_aliases(self):
        self.assertEqual(rule_validation.normalise(" POS "), "positive")
        self.assertEqual(rule_validation.normalise("-"), "negative")
        self.assertIsNone(rule_validation.normalise("maybe"))
        self.assertIsNone(rule_validation.normalise(""))


class BandSensitivityTests(unittest.TestCase):
    def test_wider_band_moves_scores_to_neutral(self):
        rows = [(0.07, 0.08, "none"),        # both positive at 0.05, both neutral at 0.10
                (0.60, 0.40, "none"),        # unchanged
                (0.60, -0.60, "none")]       # hard conflict at both bands
        counts, changed, total = band.tally(rows, [0.05, 0.10], 0.5)
        self.assertEqual(total, 3)
        self.assertEqual(counts[0.05]["vader"]["positive"], 3)
        self.assertEqual(counts[0.10]["vader"]["positive"], 2)
        self.assertEqual(counts[0.10]["vader"]["neutral"], 1)
        self.assertEqual(changed[("positive", "neutral")], 1)
        self.assertEqual(counts[0.05]["ambiguous"][1], 1)
        self.assertEqual(counts[0.10]["ambiguous"][1], 1)


if __name__ == "__main__":
    unittest.main()
