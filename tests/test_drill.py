"""Pure helpers of the dashboard drill-down (dashboard/drill.py): no database, no browser."""

import datetime as dt
import unittest

import pandas as pd

from dashboard import drill


def epoch(year, month, day, hour=0):
    return int(dt.datetime(year, month, day, hour, tzinfo=dt.timezone.utc).timestamp())


def sample():
    rows = [(epoch(2024, 12, 30), 1, 10), (epoch(2024, 12, 30, 5), 2, 20), (epoch(2025, 1, 1), 1, 5),
            (epoch(2025, 1, 6, 13), 2, 7), (epoch(2025, 3, 5, 14), 1, 100), (epoch(2025, 3, 5, 15), 2, 1)]
    return pd.DataFrame(rows, columns=["hour_utc", "source_id", "value"])


class TimeFrameTests(unittest.TestCase):
    def test_levels_follow_dimtime(self):
        frame = drill.time_frame(sample())
        first = frame.iloc[0]
        # DimTime holds Year 2024, Month 12, Week 1 (ISO), Day 30 for 2024-12-30: the week belongs to ISO year 2025
        self.assertEqual((first.year, first.month, first.week, first.day, first.hour), (2024, 12, 1, "2024-12-30", 0))
        self.assertEqual(frame.iloc[4].week, 10)
        self.assertEqual(frame.iloc[4].hour, 14)

    def test_input_is_not_modified(self):
        raw = sample()
        drill.time_frame(raw)
        self.assertEqual(list(raw.columns), ["hour_utc", "source_id", "value"])


class LevelTotalsTests(unittest.TestCase):
    def setUp(self):
        self.frame = drill.time_frame(sample())

    def test_every_level_adds_up_to_its_parent(self):
        total = self.frame.value.sum()
        years = drill.level_totals(self.frame, drill.TIME_LEVELS, [])
        self.assertEqual(years.value.sum(), total)
        self.assertEqual(dict(zip(years.year, years.value)), {2024: 30, 2025: 113})
        months = drill.level_totals(self.frame, drill.TIME_LEVELS, [2025])
        self.assertEqual(dict(zip(months.month, months.value)), {1: 12, 3: 101})
        weeks = drill.level_totals(self.frame, drill.TIME_LEVELS, [2025, 1])
        self.assertEqual(dict(zip(weeks.week, weeks.value)), {1: 5, 2: 7})
        days = drill.level_totals(self.frame, drill.TIME_LEVELS, [2025, 3, 10])
        self.assertEqual(list(days.day), ["2025-03-05"])
        hours = drill.level_totals(self.frame, drill.TIME_LEVELS, [2025, 3, 10, "2025-03-05"])
        self.assertEqual(dict(zip(hours.hour, hours.value)), {14: 100, 15: 1})

    def test_a_week_that_spans_two_months_is_split_by_month(self):
        frame = drill.time_frame(pd.DataFrame({"hour_utc": [epoch(2025, 3, 31), epoch(2025, 4, 1)], "value": [3, 4]}))
        march = drill.level_totals(frame, drill.TIME_LEVELS, [2025, 3])
        april = drill.level_totals(frame, drill.TIME_LEVELS, [2025, 4])
        self.assertEqual((march.week.tolist(), march.value.tolist()), ([14], [3]))
        self.assertEqual((april.week.tolist(), april.value.tolist()), ([14], [4]))

    def test_source_levels(self):
        src = pd.DataFrame({"source_id": [1, 2], "platform": ["Reddit", "Reddit"], "subreddit": ["r/stocks", "r/stocks"],
                            "content_type": ["Post", "Comment"]})
        frame = sample().merge(src, on="source_id")
        by_type = drill.level_totals(frame, drill.SOURCE_LEVELS, ["Reddit", "r/stocks"])
        self.assertEqual(dict(zip(by_type.content_type, by_type.value)), {"Post": 115, "Comment": 28})


class LabelTests(unittest.TestCase):
    def test_labels(self):
        frame = drill.time_frame(sample())
        self.assertEqual(drill.default_label("month", 3, frame), "มี.ค.")
        self.assertEqual(drill.default_label("hour", 7, frame), "07:00")
        self.assertEqual(drill.default_label("day", "2025-03-05", frame), "5 มี.ค. (พ.)")        # a Wednesday
        self.assertEqual(drill.default_label("content_type", "Comment", frame), "ความคิดเห็น")
        week = drill.default_label("week", 10, frame[frame.month == 3])
        self.assertEqual(week, "สัปดาห์ที่ 10 (5 มี.ค.–5 มี.ค.)")


if __name__ == "__main__":
    unittest.main()
