# Stock App — TODO Tracker

---

## T212 Pies (UI already built — backend contracts needed)

- [ ] `get_pie_list() -> list[dict]` on `TradingAccount` in `api/trading212.py`
  - Wrap `get_all_pies()` and return `[{"id": str, "name": str}, ...]`
  - UI pie selector dropdown calls `TickerDB().get_pie_list()` — inherited automatically
- [ ] `add_stocks_to_pie(pie_id: str, selections: dict[str, float])` on `TickerDB` in `data_functions/ticker_db.py`
  - `selections` is `{ticker_string: weight_as_decimal}` e.g. `{"AAPL": 0.60}` — weights sum to 1.0, enforced by UI
  - Step 1: resolve each ticker string to the T212 instrument format via `get_by_ticker()`
  - Step 2: decide merge vs replace (see note on `update_pie` in `api/trading212.py`)
  - Step 3: validate weights with `take_pct()` before building payload
  - Step 4: call `self.update_pie(pie_id, instrument_shares_dict)`

---

## TickerDB — Stub Methods to Implement

- [ ] `get_by_currency(currency_code: str)` — all instruments in a given currency e.g. "GBP"
- [ ] `get_extended_hours(extended_hours: bool)` — instruments where extendedHours is True
- [ ] `get_by_type(type: str)` — filter by type e.g. "ETF", "STOCK"
- [ ] `search_by_name(name: str)` — fuzzy search on the name field
- [ ] `filter_tradeables(isin_list: list)` — given a list of ISINs return which are on T212
- [ ] `get_max_quantity(isin: str)` — return maxOpenQuantity for an instrument

---

## Known Issues

- Module-level debug code in `data_functions/ticker_db.py` (lines 153–155) runs on every
  import. Remove or guard with `if __name__ == "__main__":` when tidying up.


Intergration testing on the API calls 
class methods
some kind of advanced data structure and searching algo
generators
