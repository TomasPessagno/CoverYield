"""Ticker universe: liquid, optionable US stocks and ETFs.

This curated list backs the ticker picker and the multi-stock scan. A larger
universe (e.g. S&P 500 membership) can be added here later.
"""

# Popular tickers for covered call screening (high-volume, liquid options)
# Format: {symbol: company_name}
TICKER_MAP: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "META": "Meta Platforms Inc.",
    "NVDA": "NVIDIA Corp.",
    "TSLA": "Tesla Inc.",
    "AMD": "Advanced Micro Devices",
    "INTC": "Intel Corp.",
    "NFLX": "Netflix Inc.",
    "DIS": "Walt Disney Co.",
    "BA": "Boeing Co.",
    "JPM": "JPMorgan Chase & Co.",
    "V": "Visa Inc.",
    "MA": "Mastercard Inc.",
    "WMT": "Walmart Inc.",
    "KO": "Coca-Cola Co.",
    "PEP": "PepsiCo Inc.",
    "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer Inc.",
    "XOM": "Exxon Mobil Corp.",
    "CVX": "Chevron Corp.",
    "MRK": "Merck & Co.",
    "ABBV": "AbbVie Inc.",
    "UNH": "UnitedHealth Group",
    "HD": "Home Depot Inc.",
    "MCD": "McDonald's Corp.",
    "CRM": "Salesforce Inc.",
    "ORCL": "Oracle Corp.",
    "CSCO": "Cisco Systems",
    "QCOM": "Qualcomm Inc.",
    "AVGO": "Broadcom Inc.",
    "TXN": "Texas Instruments",
    "COST": "Costco Wholesale",
    "SBUX": "Starbucks Corp.",
    "NKE": "Nike Inc.",
    "LOW": "Lowe's Companies",
    "T": "AT&T Inc.",
    "VZ": "Verizon Communications",
    "UBER": "Uber Technologies",
    "PYPL": "PayPal Holdings",
    "SQ": "Block Inc.",
    "SNAP": "Snap Inc.",
    "COIN": "Coinbase Global",
    "PLTR": "Palantir Technologies",
    "SOFI": "SoFi Technologies",
    "RIVN": "Rivian Automotive",
    "LCID": "Lucid Group",
    "SPY": "SPDR S&P 500 ETF",
    "QQQ": "Invesco QQQ Trust",
    "IWM": "iShares Russell 2000",
    "DIA": "SPDR Dow Jones ETF",
    "EEM": "iShares MSCI Emerging",
    "XLF": "Financial Select SPDR",
    "XLE": "Energy Select SPDR",
    "XLK": "Technology Select SPDR",
}

# Default universe for the multi-stock scan.
DEFAULT_UNIVERSE: list[str] = list(TICKER_MAP)
