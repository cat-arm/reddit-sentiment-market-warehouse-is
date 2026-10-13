import copy
import unittest
from collections import Counter

from etl.ticker_dict import TickerMatcher, load_tickers, validate
from market_fetch import TICKERS


class TickerConfigTest(unittest.TestCase):
    def test_config_covers_exactly_the_34_target_tickers(self):
        config = load_tickers()
        self.assertEqual(len(config["tickers"]), 34)
        self.assertEqual(set(config["tickers"]), set(TICKERS))

    def test_asset_class_split_matches_the_proposal_groups(self):
        classes = Counter(spec["asset_class"] for spec in load_tickers()["tickers"].values())
        self.assertEqual(classes, {"stock_etf": 22, "crypto": 6, "futures": 6})
        for symbol, spec in load_tickers()["tickers"].items():
            if symbol.endswith("-USD"):
                self.assertEqual(spec["asset_class"], "crypto")
            if symbol.endswith("=F"):
                self.assertEqual(spec["asset_class"], "futures")

    def test_config_is_valid_and_every_ticker_can_be_found(self):
        config = load_tickers()
        self.assertEqual(validate(config), [])
        for symbol, spec in config["tickers"].items():
            self.assertTrue(spec["aliases"] or spec["cashtags"], symbol)

    def test_validate_reports_alias_shared_by_two_tickers_and_bad_class(self):
        config = copy.deepcopy(load_tickers())
        config["tickers"]["MSFT"]["aliases"].append("Tesla")
        config["tickers"]["AAPL"]["asset_class"] = "bonds"
        problems = validate(config)
        self.assertTrue(any("Tesla" in p for p in problems))
        self.assertTrue(any("asset_class" in p for p in problems))
        with self.assertRaises(ValueError):
            TickerMatcher(config)


class TickerMatchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matcher = TickerMatcher()

    def find(self, text, subreddit=None, **kwargs):
        return dict(self.matcher.find(text, subreddit, **kwargs))

    def test_counts_every_mention_and_both_symbol_and_name(self):
        self.assertEqual(self.find("TSLA TSLA and Tesla"), {"TSLA": 3})
        self.assertEqual(self.find("$TSLA Tesla"), {"TSLA": 2})

    def test_cashtag_is_counted_once_and_trailing_period_is_ignored(self):
        self.assertEqual(self.find("Buy $AAPL now"), {"AAPL": 1})
        self.assertEqual(self.find("I like $NVDA."), {"NVDA": 1})

    def test_dollar_amounts_are_not_cashtags(self):
        self.assertEqual(self.find("I made $100 and $5k today"), {})

    def test_apple_needs_the_capital_letter(self):
        self.assertEqual(self.find("Apple earnings were great"), {"AAPL": 1})
        self.assertEqual(self.find("I ate an apple pie"), {})

    def test_ko_the_boxing_term_is_not_coca_cola(self):
        for text in ("He won by KO in round 2", "ko'd him", "KO!", "ko"):
            self.assertEqual(self.find(text), {}, text)
        self.assertEqual(self.find("$KO is a dividend stock"), {"KO": 1})
        self.assertEqual(self.find("Coca-Cola and Coca Cola and CocaCola"), {"KO": 3})

    def test_coin_the_word_is_not_coinbase(self):
        for text in ("flip a coin", "BUY COIN NOW", "coin toss"):
            self.assertEqual(self.find(text), {}, text)
        self.assertEqual(self.find("Coinbase is down"), {"COIN": 1})
        self.assertEqual(self.find("$COIN earnings"), {"COIN": 1})

    def test_sol_needs_cashtag_or_solana(self):
        self.assertEqual(self.find("Sol went home early"), {})
        self.assertEqual(self.find("$SOL pumping"), {"SOL-USD": 1})
        self.assertEqual(self.find("Solana is fast"), {"SOL-USD": 1})

    def test_doge_only_counts_in_the_crypto_community(self):
        self.assertEqual(self.find("doge to the moon", "CryptoCurrency"), {"DOGE-USD": 1})
        self.assertEqual(self.find("DOGE cuts spending", "stocks"), {})
        self.assertEqual(self.find("doge", None), {})
        self.assertEqual(self.find("Dogecoin", "stocks"), {"DOGE-USD": 1})
        self.assertEqual(self.find("$DOGE", "stocks"), {"DOGE-USD": 1})

    def test_ripple_effect_is_not_xrp(self):
        self.assertEqual(self.find("The ripple effect is real"), {})
        self.assertEqual(self.find("Ripple effect is real"), {})
        self.assertEqual(self.find("Ripple got sued"), {"XRP-USD": 1})
        self.assertEqual(self.find("XRP up 10%"), {"XRP-USD": 1})

    def test_hood_and_mara_are_not_ordinary_words(self):
        for text in ("Robin Hood stole from the rich", "the hood is rough", "Mara went to school"):
            self.assertEqual(self.find(text), {}, text)
        self.assertEqual(self.find("HOOD earnings"), {"HOOD": 1})
        self.assertEqual(self.find("Robinhood app down"), {"HOOD": 1})
        self.assertEqual(self.find("MARA miners and Marathon Digital"), {"MARA": 2})

    def test_word_boundaries(self):
        self.assertEqual(self.find("SPY 450 calls and TQQQ and QQQ"), {"SPY": 1, "QQQ": 1})
        self.assertEqual(self.find("AMDOCS rallied"), {})
        self.assertEqual(self.find("AMD's earnings"), {"AMD": 1})

    def test_futures_are_found_by_phrase_or_slash_symbol_not_bare_letters(self):
        self.assertEqual(self.find("/ES is holding 5000"), {"ES=F": 1})
        self.assertEqual(self.find("ES"), {})
        self.assertEqual(self.find("es is a word in spanish"), {})
        self.assertEqual(self.find("S&P 500 futures are green"), {"ES=F": 1})
        self.assertEqual(self.find("Nasdaq futures down"), {"NQ=F": 1})
        self.assertEqual(self.find("natural gas spiked"), {"NG=F": 1})
        self.assertEqual(self.find("crude oil at $80"), {"CL=F": 1})
        self.assertEqual(self.find("gold futures rally"), {"GC=F": 1})
        self.assertEqual(self.find("Russell 2000 futures"), {"RTY=F": 1})      # not counted twice

    def test_weak_aliases_can_be_excluded(self):
        self.assertEqual(self.find("gold is up"), {"GC=F": 1})
        self.assertEqual(self.find("gold is up", include_weak=False), {})

    def test_berkshire_and_johnson_variants(self):
        self.assertEqual(self.find("BRK.B, BRK-B, Berkshire Hathaway"), {"BRK-B": 3})
        self.assertEqual(self.find("Johnson & Johnson and J&J"), {"JNJ": 2})

    def test_asset_class_lookup(self):
        self.assertEqual(self.matcher.asset_class["BTC-USD"], "crypto")
        self.assertEqual(self.matcher.asset_class["GC=F"], "futures")
        self.assertEqual(self.matcher.asset_class["COIN"], "stock_etf")
        self.assertEqual(len(self.matcher.symbols), 34)


if __name__ == "__main__":
    unittest.main()
