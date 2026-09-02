"""Datenquelle yfinance — ohne API-Schlüssel, auch für Xetra-Werte.

Ersetzt financialdatasets.ai als Standardquelle. Die Funktionen hier haben
dieselben Signaturen und Rückgabetypen wie die in ``api.py``, damit die
Agenten nichts davon merken.

Grenzen, die bewusst so bleiben:

* **Insider-Geschäfte gibt es nur für US-Werte.** Das sind SEC-Meldungen
  (Form 4). Für DAX-Titel kommt eine leere Liste zurück, weil es diese
  Meldepflicht dort nicht gibt. Kein Anbieter löst das gratis.
* **Kein Point-in-Time.** yfinance liefert keine Einreichungsdaten. Wir
  filtern nach Ende der Berichtsperiode, nicht nach Veröffentlichung. Für
  eine Analyse von heute ist das richtig, für einen Backtest über Jahre
  entsteht ein leichter Blick nach vorn.
* **Kennzahlen werden gerechnet, nicht geliefert.** Margen, Renditen und
  Wachstumsraten entstehen hier aus den Rohwerten der Abschlüsse.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os

import pandas as pd
import yfinance as yf

from src.data.models import (
    CompanyNews,
    FinancialMetrics,
    InsiderTrade,
    LineItem,
    Price,
)

logger = logging.getLogger(__name__)

# Ein Ticker wird oft mehrfach hintereinander abgefragt. Ohne diesen Zwischen-
# speicher zieht ein Lauf mit 14 Agenten dieselben Abschlüsse dutzendfach.
_CACHE: dict[str, object] = {}


def _ticker(symbol: str) -> yf.Ticker:
    key = f"t:{symbol}"
    if key not in _CACHE:
        _CACHE[key] = yf.Ticker(symbol)
    return _CACHE[key]


def _frame(symbol: str, attr: str) -> pd.DataFrame:
    """Einen Abschluss holen und merken. Leerer Frame statt Ausnahme."""
    key = f"{attr}:{symbol}"
    if key not in _CACHE:
        try:
            df = getattr(_ticker(symbol), attr)
            _CACHE[key] = df if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except Exception as exc:  # yfinance wirft je nach Fehler alles Mögliche
            logger.warning("yfinance %s für %s nicht verfügbar: %s", attr, symbol, exc)
            _CACHE[key] = pd.DataFrame()
    return _CACHE[key]


def _info(symbol: str) -> dict:
    key = f"info:{symbol}"
    if key not in _CACHE:
        try:
            _CACHE[key] = _ticker(symbol).info or {}
        except Exception as exc:
            logger.warning("yfinance info für %s nicht verfügbar: %s", symbol, exc)
            _CACHE[key] = {}
    return _CACHE[key]


def _num(value) -> float | None:
    """Zahl oder None. NaN gilt als nicht vorhanden."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _pick(df: pd.DataFrame, column, *names: str) -> float | None:
    """Ersten Treffer aus mehreren möglichen Zeilennamen holen.

    yfinance benennt dieselbe Position je nach Titel unterschiedlich, deshalb
    steht hier eine Liste statt eines festen Namens.
    """
    if df.empty or column is None:
        return None
    for name in names:
        if name in df.index:
            return _num(df.at[name, column])
    return None


def _columns_until(df: pd.DataFrame, end_date: str | None) -> list:
    """Spalten (Perioden) bis einschließlich end_date, neueste zuerst."""
    if df.empty:
        return []
    cols = list(df.columns)
    if end_date:
        try:
            cutoff = pd.Timestamp(end_date)
            cols = [c for c in cols if pd.Timestamp(c) <= cutoff]
        except Exception:
            pass
    return sorted(cols, key=lambda c: pd.Timestamp(c), reverse=True)


def _sum_last_quarters(df: pd.DataFrame, cols: list, *names: str, count: int = 4) -> float | None:
    """Flussgröße über die letzten Quartale summieren (TTM)."""
    values = [_pick(df, c, *names) for c in cols[:count]]
    values = [v for v in values if v is not None]
    if len(values) < count:
        return None
    return sum(values)


# ---------------------------------------------------------------------------
# Kurse
# ---------------------------------------------------------------------------

def get_prices(ticker: str, start_date: str, end_date: str, api_key: str = None) -> list[Price]:
    """Tageskurse. ``api_key`` wird ignoriert, yfinance braucht keinen."""
    try:
        hist = _ticker(ticker).history(start=start_date, end=end_date, auto_adjust=False)
    except Exception as exc:
        logger.warning("yfinance Kurse für %s nicht verfügbar: %s", ticker, exc)
        return []
    if hist is None or hist.empty:
        return []

    prices: list[Price] = []
    for idx, row in hist.iterrows():
        close = _num(row.get("Close"))
        if close is None:
            continue
        prices.append(
            Price(
                open=_num(row.get("Open")) or close,
                close=close,
                high=_num(row.get("High")) or close,
                low=_num(row.get("Low")) or close,
                volume=int(_num(row.get("Volume")) or 0),
                time=pd.Timestamp(idx).strftime("%Y-%m-%d"),
            )
        )
    return prices


# ---------------------------------------------------------------------------
# Marktkapitalisierung
# ---------------------------------------------------------------------------

def get_market_cap(ticker: str, end_date: str, api_key: str = None) -> float | None:
    """Marktkapitalisierung.

    Für heute nimmt yfinance den Live-Wert. Für ein Datum in der Vergangenheit
    rechnen wir Schlusskurs mal Aktienzahl, sonst bekäme ein Rückblick den
    heutigen Wert untergeschoben.
    """
    info = _info(ticker)
    heute = _dt.date.today().isoformat()

    if not end_date or end_date >= heute:
        cap = _num(info.get("marketCap"))
        if cap:
            return cap

    shares = _num(info.get("sharesOutstanding"))
    if not shares:
        bs = _frame(ticker, "balance_sheet")
        cols = _columns_until(bs, end_date)
        if cols:
            shares = _pick(bs, cols[0], "Ordinary Shares Number", "Share Issued")
    if not shares:
        return _num(info.get("marketCap"))

    try:
        start = (pd.Timestamp(end_date) - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        hist = _ticker(ticker).history(start=start, end=end_date, auto_adjust=False)
        if hist is not None and not hist.empty:
            close = _num(hist["Close"].iloc[-1])
            if close:
                return close * shares
    except Exception as exc:
        logger.warning("Marktkapitalisierung für %s nicht rechenbar: %s", ticker, exc)
    return _num(info.get("marketCap"))


# ---------------------------------------------------------------------------
# Bilanzpositionen
# ---------------------------------------------------------------------------

# Was die Agenten anfragen, und wie es bei yfinance heißt. Mehrere Namen je
# Position, weil die Bezeichnung je nach Unternehmen wechselt.
_INCOME = {
    "revenue": ("Total Revenue", "Operating Revenue"),
    "net_income": ("Net Income", "Net Income Common Stockholders",
                   "Net Income From Continuing Operation Net Minority Interest"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income", "Total Operating Income As Reported"),
    "operating_expense": ("Operating Expense", "Total Expenses"),
    "ebit": ("EBIT",),
    "ebitda": ("EBITDA", "Normalized EBITDA"),
    "interest_expense": ("Interest Expense", "Interest Expense Non Operating"),
    "research_and_development": ("Research And Development",),
    "earnings_per_share": ("Basic EPS", "Diluted EPS"),
}

_BALANCE = {
    "total_assets": ("Total Assets",),
    "total_liabilities": ("Total Liabilities Net Minority Interest", "Total Liabilities"),
    "shareholders_equity": ("Stockholders Equity", "Total Equity Gross Minority Interest"),
    "total_debt": ("Total Debt",),
    "cash_and_equivalents": ("Cash And Cash Equivalents",
                             "Cash Cash Equivalents And Short Term Investments"),
    "current_assets": ("Current Assets", "Total Current Assets"),
    "current_liabilities": ("Current Liabilities", "Total Current Liabilities"),
    "goodwill_and_intangible_assets": ("Goodwill And Other Intangible Assets",),
    "intangible_assets": ("Goodwill And Other Intangible Assets", "Other Intangible Assets"),
    "outstanding_shares": ("Ordinary Shares Number", "Share Issued"),
}

_CASHFLOW = {
    "capital_expenditure": ("Capital Expenditure", "Purchase Of PPE"),
    "depreciation_and_amortization": ("Depreciation And Amortization",
                                      "Depreciation Amortization Depletion"),
    "free_cash_flow": ("Free Cash Flow",),
    "dividends_and_other_cash_distributions": ("Cash Dividends Paid", "Common Stock Dividend Paid"),
    "issuance_or_purchase_of_equity_shares": ("Repurchase Of Capital Stock",
                                              "Net Common Stock Issuance"),
    "net_cash_flow_from_operations": ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
}

# Bestandsgrößen. Sie werden nicht über vier Quartale summiert, sondern zum
# Stichtag genommen. Alles andere wäre die vierfache Bilanzsumme.
_BESTAND = set(_BALANCE) | {"earnings_per_share"}


def _quelle(feld: str) -> tuple[str, tuple[str, ...]] | None:
    if feld in _INCOME:
        return "income", _INCOME[feld]
    if feld in _BALANCE:
        return "balance", _BALANCE[feld]
    if feld in _CASHFLOW:
        return "cash", _CASHFLOW[feld]
    return None


def _abschluesse(ticker: str, quartalsweise: bool) -> dict[str, pd.DataFrame]:
    p = "quarterly_" if quartalsweise else ""
    return {
        "income": _frame(ticker, f"{p}income_stmt"),
        "balance": _frame(ticker, f"{p}balance_sheet"),
        "cash": _frame(ticker, f"{p}cashflow"),
    }


def _wert(feld: str, frames: dict, cols: dict, ttm: bool) -> float | None:
    """Einen Rohwert holen, direkt oder gerechnet."""
    q = _quelle(feld)
    if q:
        art, namen = q
        df, spalten = frames[art], cols[art]
        if not spalten:
            return None
        if ttm and feld not in _BESTAND:
            summe = _sum_last_quarters(df, spalten, *namen)
            if summe is not None:
                return summe
        return _pick(df, spalten[0], *namen)

    # Abgeleitete Größen
    if feld == "working_capital":
        ca = _wert("current_assets", frames, cols, ttm)
        cl = _wert("current_liabilities", frames, cols, ttm)
        return None if ca is None or cl is None else ca - cl
    if feld == "book_value_per_share":
        eq = _wert("shareholders_equity", frames, cols, ttm)
        sh = _wert("outstanding_shares", frames, cols, ttm)
        return None if not eq or not sh else eq / sh
    if feld == "gross_margin":
        gp = _wert("gross_profit", frames, cols, ttm)
        rev = _wert("revenue", frames, cols, ttm)
        return None if gp is None or not rev else gp / rev
    if feld == "operating_margin":
        oi = _wert("operating_income", frames, cols, ttm)
        rev = _wert("revenue", frames, cols, ttm)
        return None if oi is None or not rev else oi / rev
    if feld == "net_margin":
        ni = _wert("net_income", frames, cols, ttm)
        rev = _wert("revenue", frames, cols, ttm)
        return None if ni is None or not rev else ni / rev
    if feld == "debt_to_equity":
        td = _wert("total_debt", frames, cols, ttm)
        eq = _wert("shareholders_equity", frames, cols, ttm)
        return None if td is None or not eq else td / eq
    if feld == "return_on_invested_capital":
        ebit = _wert("ebit", frames, cols, ttm)
        td = _wert("total_debt", frames, cols, ttm) or 0.0
        eq = _wert("shareholders_equity", frames, cols, ttm)
        if ebit is None or not eq:
            return None
        kapital = td + eq
        return None if not kapital else ebit / kapital
    return None


def search_line_items(
    ticker: str,
    line_items: list[str],
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[LineItem]:
    """Beliebige Bilanzpositionen, eine Zeile je Berichtsperiode."""
    ttm = period == "ttm"
    frames = _abschluesse(ticker, quartalsweise=ttm)
    if all(df.empty for df in frames.values()):
        # Manche Titel liefern keine Quartale. Dann Jahreszahlen nehmen.
        frames = _abschluesse(ticker, quartalsweise=False)
        ttm = False

    cols = {k: _columns_until(df, end_date) for k, df in frames.items()}
    perioden = cols["income"] or cols["balance"] or cols["cash"]
    if not perioden:
        return []

    waehrung = _info(ticker).get("financialCurrency") or _info(ticker).get("currency") or "USD"

    ergebnis: list[LineItem] = []
    for versatz, periode in enumerate(perioden[:limit]):
        # Für jede Periode die Spalten so verschieben, dass "die letzten vier
        # Quartale" ab dieser Periode gelten und nicht ab heute.
        verschoben = {k: v[versatz:] for k, v in cols.items()}
        felder = {}
        for feld in line_items:
            wert = _wert(feld, frames, verschoben, ttm)
            if wert is not None:
                felder[feld] = wert
        ergebnis.append(
            LineItem(
                ticker=ticker,
                report_period=pd.Timestamp(periode).strftime("%Y-%m-%d"),
                period=period,
                currency=waehrung,
                **felder,
            )
        )
    return ergebnis


# ---------------------------------------------------------------------------
# Kennzahlen
# ---------------------------------------------------------------------------

def get_financial_metrics(
    ticker: str,
    end_date: str,
    period: str = "ttm",
    limit: int = 10,
    api_key: str = None,
) -> list[FinancialMetrics]:
    """Kennzahlen je Berichtsperiode, aus den Rohwerten gerechnet."""
    ttm = period == "ttm"
    frames = _abschluesse(ticker, quartalsweise=ttm)
    if all(df.empty for df in frames.values()):
        frames = _abschluesse(ticker, quartalsweise=False)
        ttm = False

    cols = {k: _columns_until(df, end_date) for k, df in frames.items()}
    perioden = cols["income"] or cols["balance"] or cols["cash"]
    if not perioden:
        return []

    info = _info(ticker)
    waehrung = info.get("financialCurrency") or info.get("currency") or "USD"
    marktkap = get_market_cap(ticker, end_date)

    def hole(feld, versatz):
        return _wert(feld, frames, {k: v[versatz:] for k, v in cols.items()}, ttm)

    def teile(a, b):
        return None if a is None or not b else a / b

    def wachstum(feld, versatz):
        jetzt, vorher = hole(feld, versatz), hole(feld, versatz + 1)
        if jetzt is None or not vorher:
            return None
        return (jetzt - vorher) / abs(vorher)

    ergebnis: list[FinancialMetrics] = []
    for versatz, periode in enumerate(perioden[:limit]):
        revenue = hole("revenue", versatz)
        net_income = hole("net_income", versatz)
        equity = hole("shareholders_equity", versatz)
        assets = hole("total_assets", versatz)
        ebitda = hole("ebitda", versatz)
        ebit = hole("ebit", versatz)
        debt = hole("total_debt", versatz)
        cash = hole("cash_and_equivalents", versatz)
        fcf = hole("free_cash_flow", versatz)
        shares = hole("outstanding_shares", versatz)
        ca = hole("current_assets", versatz)
        cl = hole("current_liabilities", versatz)
        eps = hole("earnings_per_share", versatz)
        zinsen = hole("interest_expense", versatz)
        dividenden = hole("dividends_and_other_cash_distributions", versatz)

        ev = None
        if marktkap is not None:
            ev = marktkap + (debt or 0.0) - (cash or 0.0)

        kgv = teile(marktkap, net_income)
        kbv = teile(marktkap, equity)
        wachstum_gewinn = wachstum("net_income", versatz)

        ergebnis.append(
            FinancialMetrics(
                ticker=ticker,
                report_period=pd.Timestamp(periode).strftime("%Y-%m-%d"),
                period=period,
                currency=waehrung,
                market_cap=marktkap,
                enterprise_value=ev,
                price_to_earnings_ratio=kgv,
                price_to_book_ratio=kbv,
                price_to_sales_ratio=teile(marktkap, revenue),
                enterprise_value_to_ebitda_ratio=teile(ev, ebitda),
                enterprise_value_to_revenue_ratio=teile(ev, revenue),
                free_cash_flow_yield=teile(fcf, marktkap),
                peg_ratio=(kgv / (wachstum_gewinn * 100)
                           if kgv and wachstum_gewinn and wachstum_gewinn > 0 else None),
                gross_margin=teile(hole("gross_profit", versatz), revenue),
                operating_margin=teile(hole("operating_income", versatz), revenue),
                net_margin=teile(net_income, revenue),
                return_on_equity=teile(net_income, equity),
                return_on_assets=teile(net_income, assets),
                return_on_invested_capital=hole("return_on_invested_capital", versatz),
                asset_turnover=teile(revenue, assets),
                inventory_turnover=None,
                receivables_turnover=None,
                days_sales_outstanding=None,
                operating_cycle=None,
                working_capital_turnover=teile(
                    revenue, (ca - cl) if ca is not None and cl is not None else None),
                current_ratio=teile(ca, cl),
                quick_ratio=teile(cash, cl),
                cash_ratio=teile(cash, cl),
                operating_cash_flow_ratio=teile(
                    hole("net_cash_flow_from_operations", versatz), cl),
                debt_to_equity=teile(debt, equity),
                debt_to_assets=teile(debt, assets),
                interest_coverage=teile(ebit, abs(zinsen) if zinsen else None),
                revenue_growth=wachstum("revenue", versatz),
                earnings_growth=wachstum_gewinn,
                book_value_growth=wachstum("shareholders_equity", versatz),
                earnings_per_share_growth=wachstum("earnings_per_share", versatz),
                free_cash_flow_growth=wachstum("free_cash_flow", versatz),
                operating_income_growth=wachstum("operating_income", versatz),
                ebitda_growth=wachstum("ebitda", versatz),
                payout_ratio=(teile(abs(dividenden), net_income) if dividenden else None),
                earnings_per_share=eps,
                book_value_per_share=teile(equity, shares),
                free_cash_flow_per_share=teile(fcf, shares),
            )
        )
    return ergebnis


# ---------------------------------------------------------------------------
# Insider-Geschäfte
# ---------------------------------------------------------------------------

def get_insider_trades(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[InsiderTrade]:
    """Insider-Geschäfte. Nur US-Titel, das sind SEC-Meldungen.

    Für DAX-Werte kommt hier eine leere Liste zurück. Das ist keine Panne,
    sondern die Rechtslage: eine Form-4-Meldepflicht gibt es dort nicht.
    """
    try:
        df = _ticker(ticker).insider_transactions
    except Exception as exc:
        logger.warning("Insider-Daten für %s nicht verfügbar: %s", ticker, exc)
        return []
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []

    spalten = {str(c).lower(): c for c in df.columns}

    def hole(zeile, *kandidaten):
        for k in kandidaten:
            if k in spalten:
                return zeile.get(spalten[k])
        return None

    trades: list[InsiderTrade] = []
    for _, zeile in df.iterrows():
        datum = hole(zeile, "start date", "date")
        try:
            datum_s = pd.Timestamp(datum).strftime("%Y-%m-%d") if datum is not None else None
        except Exception:
            datum_s = None
        if datum_s:
            if end_date and datum_s > end_date:
                continue
            if start_date and datum_s < start_date:
                continue

        stueck = _num(hole(zeile, "shares"))
        wert = _num(hole(zeile, "value"))
        text = str(hole(zeile, "transaction", "text") or "")
        # Verkäufe negativ führen, so erwarten es die Agenten
        if stueck is not None and "sale" in text.lower():
            stueck = -abs(stueck)

        trades.append(
            InsiderTrade(
                ticker=ticker,
                issuer=None,
                name=(str(hole(zeile, "insider")) if hole(zeile, "insider") is not None else None),
                title=(str(hole(zeile, "position")) if hole(zeile, "position") is not None else None),
                is_board_director=None,
                transaction_date=datum_s,
                transaction_shares=stueck,
                transaction_price_per_share=(wert / abs(stueck) if wert and stueck else None),
                transaction_value=wert,
                shares_owned_before_transaction=None,
                shares_owned_after_transaction=None,
                security_title=None,
                filing_date=datum_s or (end_date or ""),
            )
        )
        if len(trades) >= limit:
            break
    return trades


# ---------------------------------------------------------------------------
# Nachrichten
# ---------------------------------------------------------------------------

def get_company_news(
    ticker: str,
    end_date: str,
    start_date: str | None = None,
    limit: int = 1000,
    api_key: str = None,
) -> list[CompanyNews]:
    """Schlagzeilen. Ohne Stimmungsbewertung, die liefert yfinance nicht."""
    try:
        roh = _ticker(ticker).news or []
    except Exception as exc:
        logger.warning("Nachrichten für %s nicht verfügbar: %s", ticker, exc)
        return []

    meldungen: list[CompanyNews] = []
    for eintrag in roh:
        inhalt = eintrag.get("content", eintrag) if isinstance(eintrag, dict) else {}
        titel = inhalt.get("title") or eintrag.get("title")
        if not titel:
            continue

        datum = (inhalt.get("pubDate") or inhalt.get("displayTime")
                 or eintrag.get("providerPublishTime"))
        try:
            if isinstance(datum, (int, float)):
                datum_s = _dt.datetime.fromtimestamp(datum).strftime("%Y-%m-%d")
            elif datum:
                datum_s = pd.Timestamp(datum).strftime("%Y-%m-%d")
            else:
                datum_s = end_date
        except Exception:
            datum_s = end_date

        if end_date and datum_s > end_date:
            continue
        if start_date and datum_s < start_date:
            continue

        anbieter = inhalt.get("provider") or {}
        quelle = (anbieter.get("displayName") if isinstance(anbieter, dict) else None) or "Yahoo Finance"
        url = ((inhalt.get("canonicalUrl") or {}).get("url")
               if isinstance(inhalt.get("canonicalUrl"), dict) else None) or eintrag.get("link") or ""

        meldungen.append(
            CompanyNews(
                ticker=ticker,
                title=str(titel),
                author=None,
                source=str(quelle),
                date=datum_s,
                url=str(url),
                sentiment=None,
            )
        )
        if len(meldungen) >= limit:
            break
    return meldungen


def cache_leeren() -> None:
    """Zwischenspeicher verwerfen. Für Tests und lange Backtests."""
    _CACHE.clear()
