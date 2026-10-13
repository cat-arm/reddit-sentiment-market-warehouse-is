"""T3: ticker dictionary for the 34 target assets and the matcher built on configs/tickers.yaml.

`TickerMatcher.find(text, subreddit)` returns {ticker: number_of_mentions}. T4 (extract_tickers.py) calls it
over processed_text. The matching rules live in the YAML file, not in code (see its header).

How matching works (so it can be checked later):
  1. cashtags ($TSLA) are found by one regex and looked up in the YAML `cashtags` lists
  2. aliases (symbol, company name, product name) are compiled into ONE big alternation per case mode
     (case-insensitive / case-sensitive); each alias is a named group g<N>, and match.lastgroup tells
     which alias hit. Longer phrases are tried first so "Coca-Cola" wins over a shorter "Coca".
  3. special rules per alias: case_sensitive (e.g. "Apple" vs "apple pie"), subreddits (e.g. doge only in
     r/CryptoCurrency), weak (generic word like "gold": counted, but can be excluded with include_weak=False)
  4. every occurrence counts (3 mentions = 3), and one text may mention several tickers
Ambiguous words that must NOT match are pinned by tests/test_ticker_dict.py (KO, COIN, SOL, Ripple effect...).
"""

import re
from collections import Counter

from etl.common import load_yaml

ASSET_CLASSES = ("stock_etf", "crypto", "futures")
# Word-boundary guards around every alias. Plain \b is not enough: "$" and "_" must also block a match.
_BEFORE = r"(?<![A-Za-z0-9_$])"          # '$' is excluded so "$AAPL" is counted once, by the cashtag rule
_AFTER = r"(?![A-Za-z0-9_])"
# "$" + 1-6 letters (optional .B style suffix); "$100" does not match because digits are not letters
_CASHTAG = re.compile(r"(?<![A-Za-z0-9_$])\$([A-Za-z]{1,6}(?:\.[A-Za-z]{1,2})?)(?![A-Za-z0-9_])")


def load_tickers():
    return load_yaml("tickers.yaml")


def _phrase_pattern(text):
    """Escape a phrase; any run of spaces/hyphens between its words matches zero or more of them."""
    words = [re.escape(word) for word in re.split(r"[\s-]+", text.strip()) if word]
    return r"[-\s]*".join(words)


def validate(config):
    """Return a list of problems found in the ticker config (empty list = valid).

    Catches mistakes that would silently corrupt counts: a wrong asset_class, a ticker nobody can find,
    the same alias given to two tickers, and regex aliases with capturing groups (they break lastgroup).
    """
    problems, seen = [], {}
    for symbol, spec in config["tickers"].items():
        if spec.get("asset_class") not in ASSET_CLASSES:
            problems.append("%s: asset_class must be one of %s" % (symbol, ASSET_CLASSES))
        if not spec.get("aliases") and not spec.get("cashtags"):
            problems.append("%s: needs at least one alias or cashtag" % symbol)
        for alias in spec.get("aliases", ()):
            entry = alias if isinstance(alias, dict) else {"text": alias}
            key = entry.get("text") or entry.get("regex")
            if not key:
                problems.append("%s: alias without text/regex: %r" % (symbol, alias))
                continue
            marker = (key if entry.get("case_sensitive") else key.lower(), tuple(entry.get("subreddits", ())))
            if marker in seen and seen[marker] != symbol:
                problems.append("alias %r is used by both %s and %s" % (key, seen[marker], symbol))
            seen[marker] = symbol
            if "regex" in entry and re.compile(entry["regex"]).groups:
                problems.append("%s: regex alias %r must not contain capturing groups" % (symbol, key))
    return problems


class TickerMatcher:
    def __init__(self, config=None):
        config = config or load_tickers()
        problems = validate(config)
        if problems:
            raise ValueError("invalid tickers.yaml: " + "; ".join(problems))
        self.symbols = tuple(config["tickers"])
        self.asset_class = {symbol: spec["asset_class"] for symbol, spec in config["tickers"].items()}
        self._cashtags = {}                            # "BTC" -> "BTC-USD", "TSLA" -> "TSLA", ...
        groups = {False: [], True: []}                 # case_sensitive -> [(pattern, info)]
        for symbol, spec in config["tickers"].items():
            for tag in spec.get("cashtags", ()):
                self._cashtags[tag.upper()] = symbol
            for alias in spec.get("aliases", ()):
                entry = alias if isinstance(alias, dict) else {"text": alias}
                pattern = entry["regex"] if "regex" in entry else _phrase_pattern(entry["text"])
                subs = frozenset(name.lower() for name in entry.get("subreddits", ())) or None
                groups[bool(entry.get("case_sensitive"))].append(
                    (pattern, (symbol, subs, bool(entry.get("weak")))))
        self._passes = []
        for sensitive, items in groups.items():
            if not items:
                continue
            items.sort(key=lambda item: -len(item[0]))            # longer phrase wins at the same position
            body = "|".join("(?P<g%d>%s)" % (n, pattern) for n, (pattern, _) in enumerate(items))
            regex = re.compile(_BEFORE + "(?:" + body + ")" + _AFTER, 0 if sensitive else re.IGNORECASE)
            self._passes.append((regex, [info for _, info in items]))

    def find_split(self, text, subreddit=None):
        """Return (strong, weak): two Counters of mentions per ticker.

        strong = clear mentions (symbol, cashtag, company/coin name); weak = generic words such as "gold".
        T4 stores both so analysis can use strong only (sensitivity check) without re-scanning 22 M texts.
        """
        strong, weak = Counter(), Counter()
        sub = subreddit.lower() if subreddit else None
        for regex, infos in self._passes:
            for match in regex.finditer(text):
                symbol, subs, is_weak = infos[int(match.lastgroup[1:])]
                if subs is not None and sub not in subs:
                    continue
                (weak if is_weak else strong)[symbol] += 1
        for match in _CASHTAG.finditer(text):
            symbol = self._cashtags.get(match.group(1).upper())
            if symbol:
                strong[symbol] += 1
        return strong, weak

    def find(self, text, subreddit=None, include_weak=True):
        """Count mentions per ticker in `text` (already cleaned by T1).

        subreddit: needed for aliases limited to some communities (doge); None = such aliases never match.
        include_weak: False drops generic-word aliases (gold, Russell 2000) = the "clear mentions only" count.
        """
        strong, weak = self.find_split(text, subreddit)
        return strong + weak if include_weak else strong
