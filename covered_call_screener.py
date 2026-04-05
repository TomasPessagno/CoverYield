"""
Covered Call Screener - Streamlit Web Application
==================================================

This app screens call options for covered call strategies by:
1. Fetching options chain data for a given ticker
2. Filtering for specific expiry windows (configurable, default 7-42 days)
3. Filtering for OTM / near-ATM calls
4. Computing static return percentages
5. Displaying filtered options that meet minimum return criteria

Author: Tomas Pessagno
"""

import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from streamlit_searchbox import st_searchbox
import altair as alt


# =============================================================================
# CONFIGURATION AND PAGE SETUP
# =============================================================================

st.set_page_config(
    page_title="Testeo de Covered Call Screener",
    layout="wide"
)

# CSS Styling (Grid table and custom fonts)
st.markdown("""
<style>
    /* Import available matching web fonts (Inter, Zilla Slab as fallback for Mozilla fonts) */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Zilla+Slab:wght@400;600;700&display=swap');

    /* Global text font stack */
    html, body, [class*="css"], [class*="st-"] {
        font-family: 'Mozilla Text', 'Inter', 'Metropolis', sans-serif !important;
    }

    /* Header font stack */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Mozilla Headline', 'Zilla Slab', 'Metropolis', 'Inter', serif !important;
        font-weight: 700 !important;
    }

    /* Grid borders for dataframe */
    .stDataFrame [data-testid="stDataFrameResizable"] {
        border: 1px solid #d1d5db;
    }
    .stDataFrame td, .stDataFrame th {
        border: 1px solid #e5e7eb !important;
    }
</style>
""", unsafe_allow_html=True)

# Popular tickers for covered call screening (high-volume, liquid options)
# Format: {symbol: company_name}
TICKER_MAP = {
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

# Build display labels: "Name (Stock Ticker)"
TICKER_OPTIONS = [f"{name} ({sym})" for sym, name in TICKER_MAP.items()]

# Reverse lookup: map lowercase company names and symbols to ticker symbols
TICKER_LOOKUP = {}
for sym, name in TICKER_MAP.items():
    TICKER_LOOKUP[sym.lower()] = sym
    TICKER_LOOKUP[name.lower()] = sym


def search_yfinance_tickers(query: str) -> list[tuple[str, str]]:
    """
    Search Yahoo Finance for tickers matching the query string.
    Returns a list of (display_label, ticker_symbol) tuples for the searchbox.
    """
    if not query or len(query) < 1:
        return []

    try:
        results = yf.Search(query, max_results=10)
        suggestions = []
        for quote in results.quotes:
            symbol = quote.get('symbol', '')
            name = quote.get('shortname', quote.get('longname', ''))
            exchange = quote.get('exchange', '')
            quote_type = quote.get('quoteType', '')

            label_parts = [symbol]
            if name:
                label_parts.append(f"— {name}")
            if exchange:
                label_parts.append(f"({exchange})")
            if quote_type and quote_type not in ('EQUITY',):
                label_parts.append(f"[{quote_type}]")

            label = " ".join(label_parts)
            suggestions.append((label, symbol))

        return suggestions
    except Exception:
        return []


# =============================================================================
# ETL STEP 1: DATA EXTRACTION - Fetch options data via yfinance
# =============================================================================

def fetch_stock_data(ticker: str) -> tuple[str, float, pd.DataFrame]:
    """
    Extract raw CALL options data for a given ticker using yfinance.

    Returns:
        tuple: (ticker, current_price, open_price, calls_df) or (ticker, 0.0, 0.0, empty_df) on error
    """
    try:
        ticker_obj = yf.Ticker(ticker)

        # Get all available expiration dates
        expirations = ticker_obj.options
        if not expirations:
            return ticker, 0.0, 0.0, pd.DataFrame()

        # Fetch CALL options for each expiration date
        all_calls = []
        for exp in expirations:
            try:
                opt_chain = ticker_obj.option_chain(exp)
                if opt_chain.calls is not None and len(opt_chain.calls) > 0:
                    calls = opt_chain.calls.copy()
                    calls['optionType'] = 'call'
                    calls['expirationDate'] = exp
                    all_calls.append(calls)
            except Exception:
                continue

        if not all_calls:
            return ticker, 0.0, 0.0, pd.DataFrame()

        # Combine all call options
        options_df = pd.concat(all_calls, ignore_index=True)

        # Get current stock price and today's open
        info = ticker_obj.info
        current_price = float(info.get('regularMarketPrice', 0))
        open_price = float(info.get('regularMarketOpen', info.get('open', 0)))

        # Convert expiration dates to datetime
        options_df['expirationDate'] = pd.to_datetime(options_df['expirationDate'])

        return ticker, current_price, open_price, options_df

    except Exception as e:
        st.error(f"Error fetching data for {ticker}: {str(e)}")
        return ticker, 0.0, 0.0, pd.DataFrame()


# =============================================================================
# ETL STEP 2: DATA TRANSFORMATION - Apply Filters and Calculate Metrics
# =============================================================================

def transform_data(
    ticker: str,
    current_price: float,
    options_df: pd.DataFrame,
    min_days_to_expiry: int,
    max_days_to_expiry: int
) -> pd.DataFrame:
    """
    Transform raw options data by applying filters and calculating metrics.

    Steps:
    1. Filter by expiration date window (min_days to max_days from today)
    2. Filter out deep ITM options (strike >= 90% of current price)
    3. Calculate static return percentage
    4. Filter by minimum target return
    """
    if options_df.empty:
        return pd.DataFrame()

    df = options_df.copy()

    # --------------------------------------------------------------------------
    # FILTER 1: Expiry Date Window (uses the actual parameters)
    # --------------------------------------------------------------------------
    today = datetime.now()
    min_expiry = today + timedelta(days=min_days_to_expiry)
    max_expiry = today + timedelta(days=max_days_to_expiry)

    df = df[
        (df['expirationDate'] >= min_expiry) &
        (df['expirationDate'] <= max_expiry)
    ].copy()

    if df.empty:
        return pd.DataFrame()

    # --------------------------------------------------------------------------
    # FILTER 2: Keep only calls (safety check — should already be calls only)
    # --------------------------------------------------------------------------
    
    df = df[df['optionType'] == 'call'].copy()

    # --------------------------------------------------------------------------
    # FILTER 3: Strike price — filter out deep ITM options
    # --------------------------------------------------------------------------

    df['Strike'] = df['strike'].round(2)
    min_strike = current_price * 0.90
    df = df[df['Strike'] >= min_strike].copy()

    # --------------------------------------------------------------------------
    # CALCULATE: Bid, Ask, Spread, Static Return %
    # --------------------------------------------------------------------------
    
    df['BidPrice'] = pd.to_numeric(
        df.get('bid', pd.Series(dtype=float)),
        errors='coerce'
    ).fillna(0)

    df['AskPrice'] = pd.to_numeric(
        df.get('ask', pd.Series(dtype=float)),
        errors='coerce'
    ).fillna(0)

    df['MidPrice'] = (df['BidPrice'] + df['AskPrice']) / 2
    df['Spread'] = df['AskPrice'] - df['BidPrice']

    if current_price > 0:
        df['Static Return %'] = (df['BidPrice'] / current_price) * 100
    else:
        df['Static Return %'] = 0.0

    # --------------------------------------------------------------------------
    # Add ticker column
    # --------------------------------------------------------------------------

    df['Ticker'] = ticker

    return df


# =============================================================================
# MAIN APP LOGIC
# =============================================================================

def main():
    """
    Main application entry point.
    Orchestrates the Streamlit UI and ETL pipeline.
    """

    # --------------------------------------------------------------------------
    # APP HEADER
    # --------------------------------------------------------------------------

    st.title("Testeo de Covered Call Screener")

    # --------------------------------------------------------------------------
    # CONFIGURATION - Inline at top of page
    # --------------------------------------------------------------------------

    st.subheader("Configuration")

    cfg_col1, cfg_col2, cfg_col3 = st.columns(3)

    with cfg_col1:
        selected_ticker = st_searchbox(
            search_yfinance_tickers,
            label="Stock Ticker",
            placeholder="Search any ticker...",
            key="ticker_searchbox",
            clear_on_submit=False,
        )
        ticker_selection = st.selectbox(
            "preset",
            options=TICKER_OPTIONS,
            index=None,
            placeholder="Or select from list...",
            key="ticker_select",
            label_visibility="collapsed"
        )

    with cfg_col2:
        min_days = st.number_input(
            "Min Days to Expiry",
            min_value=1,  # Lowered min_value slightly to allow 1-DTE strategies if the user desires
            max_value=60,
            value=7,
            key="min_days_input"
        )

    with cfg_col3:
        max_days = st.number_input(
            "Max Days to Expiry",
            min_value=14,
            max_value=90,
            value=42,
            key="max_days_input"
        )

    scan_clicked = st.button("Scan Options", type="primary", key="scan_button")

    # --------------------------------------------------------------------------
    # MAIN CONTENT AREA
    # --------------------------------------------------------------------------

    # Initialize session state
    if 'cached_data' not in st.session_state:
        st.session_state.cached_data = None  # Will store (ticker, price, df)

    # On scan click, fetch fresh data
    if scan_clicked:
        # Searchbox takes priority (returns the symbol directly)
        if selected_ticker:
            ticker = selected_ticker.strip().upper() if isinstance(selected_ticker, str) else str(selected_ticker)
        elif ticker_selection:
            ticker = ticker_selection.split("(")[-1].rstrip(")")
        else:
            ticker = ""

        if not ticker:
            st.error("Please select a ticker or type one in.")
            st.stop()

        with st.spinner(f"Fetching options data for {ticker}..."):
            result = fetch_stock_data(ticker)

        raw_ticker, current_price, open_price, options_df = result

        if current_price == 0.0 or options_df.empty:
            st.error(
                f"Could not fetch data for ticker '{ticker}'. "
                "Please verify the symbol is valid."
            )
            st.session_state.cached_data = None
            st.stop()

        # Cache the raw data in session state
        st.session_state.cached_data = {
            'ticker': ticker,
            'current_price': current_price,
            'open_price': open_price,
            'options_df': options_df,
            'scan_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC-4")
        }
        st.session_state.trigger_scroll = True

    # --------------------------------------------------------------------------
    # Display results (from cache)
    # --------------------------------------------------------------------------

    cached = st.session_state.cached_data

    if cached is None:
        st.info("Enter a ticker and click **Scan Options** to get started.")
        return

    ticker = cached['ticker']
    current_price = cached['current_price']
    open_price = cached['open_price']
    options_df = cached['options_df']
    scan_time = cached.get('scan_time', '')
    
    scan_time_html = f"<span style='font-size: 0.9rem; color: #64748b; margin-left: 15px; font-weight: 400;'>Scanned: {scan_time}</span>" if scan_time else ""

    # Transform/filter the data (runs on every rerender so layout changes apply)
    filtered_df = transform_data(
        ticker=ticker,
        current_price=current_price,
        options_df=options_df,
        min_days_to_expiry=min_days,
        max_days_to_expiry=max_days,
    )

    if filtered_df.empty:
        st.warning(
            "**No options found matching your criteria.**\n\n"
            "Try adjusting your filters or selecting a different ticker."
        )
        return

    # Auto-scroll hook (triggers only right after a scan)
    if st.session_state.get('trigger_scroll', False):
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
                // We use a slight delay to ensure layout is done.
                // window.frameElement gets the literal iframe element enclosing this script
                // inside the parent Streamlit document, making this completely bulletproof.
                setTimeout(() => {
                    window.frameElement.scrollIntoView({behavior: 'smooth', block: 'start'});
                }, 150);
            </script>
            """,
            height=0
        )
        st.session_state.trigger_scroll = False

    # Summary metrics with today's movement
    st.success(f"Found **{len(filtered_df)}** covered call opportunities for **{ticker}**")

    css_injection = "<style>\ndiv.element-container:has(#sticky-ticker-bar) {\n    position: sticky;\n    top: 2.875rem;\n    z-index: 99990;\n}\n</style>"
    
    if open_price > 0:
        day_change = current_price - open_price
        day_change_pct = (day_change / open_price) * 100
        color = "#ef4444" if day_change < 0 else "#22c55e" # Tailored red/green
        arrow = "▼" if day_change < 0 else "▲"
        
        st.markdown(
            css_injection + f"\n<div id='sticky-ticker-bar' style='padding: 10px 20px; border-radius: 8px; background-color: rgba(248, 250, 252, 0.95); backdrop-filter: blur(5px); border: 1px solid #e2e8f0; margin-bottom: 15px; display: inline-block; width: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-top: 5px;'>\n<span style='font-size: 1.2rem; font-weight: 700; margin-right: 20px;'>{ticker}</span>\n<span style='font-size: 1.1rem; margin-right: 15px; font-weight: 500;'>${current_price:.2f}</span>\n<span style='color: {color}; font-weight: 600;'>{arrow} ${abs(day_change):.2f} ({day_change_pct:+.2f}%) Today</span>{scan_time_html}\n</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            css_injection + f"\n<div id='sticky-ticker-bar' style='padding: 10px 20px; border-radius: 8px; background-color: rgba(248, 250, 252, 0.95); backdrop-filter: blur(5px); border: 1px solid #e2e8f0; margin-bottom: 15px; display: inline-block; width: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-top: 5px;'>\n<span style='font-size: 1.2rem; font-weight: 700; margin-right: 20px;'>{ticker}</span>\n<span style='font-size: 1.1rem; font-weight: 500;'>${current_price:.2f}</span>{scan_time_html}\n</div>",
            unsafe_allow_html=True
        )

    # ------------------------------------------------------------------
    # Prepare display DataFrame (copy so formatting doesn't corrupt data)
    # ------------------------------------------------------------------

    st.markdown("### Filtered Options Chain")

    # Real-time strike offset filters (filters already-loaded data, no re-fetch)
    offset_col1, offset_col2 = st.columns(2)

    with offset_col1:
        min_strike_offset = st.number_input(
            "Min Strike Offset ($)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            key="min_strike_offset_input",
            help=f"Strike ≥ ${current_price:.2f} + offset",
        )

    with offset_col2:
        max_strike_offset = st.number_input(
            "Max Strike Offset ($)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=1.0,
            key="max_strike_offset_input",
            help=f"Strike ≤ ${current_price:.2f} + offset",
        )

    return_col1, return_col2 = st.columns(2)
    with return_col1:
        min_static_return = st.slider(
            "Min Static Return %",
            min_value=0.0,
            max_value=20.0,
            value=0.0,
            step=0.5,
            key="min_static_return_slider"
        )
    with return_col2:
        min_annualized_return = st.slider(
            "Min Annualized Return %",
            min_value=0.0,
            max_value=150.0,
            value=0.0,
            step=5.0,
            key="min_annualized_return_slider"
        )

    # Calculate days to expiry
    filtered_df['Days to Expiry'] = filtered_df['expirationDate'].apply(
        lambda x: (x - datetime.now()).days
    )

    # Calculate annualized return
    filtered_df['Annualized Return %'] = filtered_df.apply(
        lambda r: r['Static Return %'] * (365 / r['Days to Expiry']) if r['Days to Expiry'] > 0 else 0.0,
        axis=1
    )

    min_strike = current_price + min_strike_offset
    max_strike = current_price + max_strike_offset
    filtered_df = filtered_df[
        (filtered_df['Strike'] >= min_strike) &
        (filtered_df['Strike'] <= max_strike) &
        (filtered_df['Static Return %'] >= min_static_return) &
        (filtered_df['Annualized Return %'] >= min_annualized_return)
    ].copy()

    if filtered_df.empty:
        st.warning("No options within this strike range. Try widening the offsets.")
        return

    # Build Strike Display column: "$155.00 ($5.00)"
    filtered_df['Strike Display'] = filtered_df['Strike'].apply(
        lambda s: f"${s:.2f} (${s - current_price:.2f})"
    )

    # Calculate breakeven price
    filtered_df['Breakeven Price'] = current_price - filtered_df['BidPrice']

    # Calculate distance to strike
    filtered_df['Distance to Strike %'] = ((filtered_df['Strike'] - current_price) / current_price) * 100

    # Clean up volume and open interest columns
    filtered_df['Volume'] = pd.to_numeric(
        filtered_df.get('volume', pd.Series(dtype=float)), errors='coerce'
    ).fillna(0).astype(int)
    filtered_df['Open Interest'] = pd.to_numeric(
        filtered_df.get('openInterest', pd.Series(dtype=float)), errors='coerce'
    ).fillna(0).astype(int)

    # Clean up implied volatility
    filtered_df['IV'] = pd.to_numeric(
        filtered_df.get('impliedVolatility', pd.Series(dtype=float)), errors='coerce'
    ).fillna(0) * 100  # Convert to percentage

    display_columns = [
        'Ticker',
        'Strike Display',
        'Distance to Strike %',
        'Days to Expiry',
        'expirationDate',
        'BidPrice',
        'MidPrice',
        'AskPrice',
        'Spread',
        'Breakeven Price',
        'Static Return %',
        'Annualized Return %',
        'Volume',
        'Open Interest',
        'IV',
    ]

    display_columns = [c for c in display_columns if c in filtered_df.columns]

    display_df = filtered_df[display_columns].copy()

    if 'expirationDate' in display_df.columns:
        display_df['expirationDate'] = display_df['expirationDate'].dt.date


    styled_df = display_df.style

    def format_dte_bar(val: float) -> str:
        if pd.isna(val): return ""
        ratio = min(max(val / max_days, 0), 1) if max_days > 0 else 0
        filled = int(ratio * 12)
        # Using a sleek minimalist wireframe track since raw text cannot be individually colored
        return f"{val:2.0f}   {'█' * filled}{'─' * (12 - filled)}"

    # Format numeric columns
    format_map = {
        'Distance to Strike %': '{:.2f}%',
        'Days to Expiry': format_dte_bar,
        'BidPrice': '${:.2f}',
        'MidPrice': '${:.2f}',
        'AskPrice': '${:.2f}',
        'Spread': '${:.2f}',
        'Breakeven Price': '${:.2f}',
        'Static Return %': '{:.2f}%',
        'Annualized Return %': '{:.2f}%',
        'Volume': '{:,.0f}',
        'Open Interest': '{:,.0f}',
        'IV': '{:.2f}%',
    }
    # Only format columns that exist in display_df
    active_formats = {k: v for k, v in format_map.items() if k in display_df.columns}
    styled_df = styled_df.format(active_formats)

    # ---------- Gradient helper functions----------

    def green_gradient(series: pd.Series, vmin: float = 0, vmax: float = 60) -> list[str]:
        """White (low) → rich green (high) with absolute boundaries."""
        styles = []
        for val in series:
            ratio = min(max((val - vmin) / (vmax - vmin), 0), 1) if vmax > vmin else 0
            r = int(255 - (255 - 30) * ratio)
            g = int(255 - (255 - 130) * ratio)
            b = int(255 - (255 - 50) * ratio)
            text_color = '#000' if ratio < 0.6 else '#fff'
            styles.append(f'background-color: rgb({r},{g},{b}); color: {text_color}')
        return styles

    def blue_gradient(series: pd.Series, vmin: float = 0, vmax: float = 20) -> list[str]:
        """White (low) → rich blue (high) with absolute boundaries."""
        styles = []
        for val in series:
            ratio = min(max((val - vmin) / (vmax - vmin), 0), 1) if vmax > vmin else 0
            r = int(255 - (255 - 20) * ratio)
            g = int(255 - (255 - 70) * ratio)
            b = int(255 - (255 - 180) * ratio)
            text_color = '#000' if ratio < 0.6 else '#fff'
            styles.append(f'background-color: rgb({r},{g},{b}); color: {text_color}')
        return styles

    def warning_gradient(series: pd.Series, vmin: float = 0, vmax: float = 1) -> list[str]:
        """White (low) → orange → dark red (high) with absolute boundaries."""
        styles = []
        for val in series:
            ratio = min(max((val - vmin) / (vmax - vmin), 0), 1) if vmax > vmin else 0
            if ratio <= 0.5:
                t = ratio * 2
                r, g, b = 255, int(255 - 95 * t), int(255 - 205 * t)
            else:
                t = (ratio - 0.5) * 2
                r = int(255 - 75 * t)
                g = int(160 - 130 * t)
                b = int(50 - 30 * t)
            text_color = '#000' if ratio < 0.5 else '#fff'
            styles.append(f'background-color: rgb({r},{g},{b}); color: {text_color}')
        return styles

    def vol_oi_heatmap(df: pd.DataFrame) -> pd.DataFrame:
        """Applies dynamic heatmap to Volume based on OI ratio, and solid gray to OI."""
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        if 'Volume' in df.columns and 'Open Interest' in df.columns:
            oi_safe = df['Open Interest'].replace({0: 1, 0.0: 1})
            ratio = (df['Volume'] / oi_safe).clip(0, 1)
            
            # White to dark gray (55, 65, 81)
            r = (255 - (255 - 55) * ratio).astype(int)
            g = (255 - (255 - 65) * ratio).astype(int)
            b = (255 - (255 - 81) * ratio).astype(int)
            
            text_colors = ['#fff' if val > 0.6 else '#000' for val in ratio]
            vol_styles = [f'background-color: rgb({r.iloc[i]},{g.iloc[i]},{b.iloc[i]}); color: {text_colors[i]}' for i in range(len(ratio))]
            
            styles['Volume'] = vol_styles
            styles['Open Interest'] = 'background-color: #f1f5f9; color: #000'
        return styles

    # ---------- Apply per-column with absolute boundaries ----------

    # Static Return %: vmin=0, vmax=10 (single-digit values get proper color)
    if 'Static Return %' in display_df.columns:
        styled_df = styled_df.apply(green_gradient, subset=['Static Return %'], vmin=0, vmax=10)

    # Annualized Return %: vmin=0, vmax=60
    if 'Annualized Return %' in display_df.columns:
        styled_df = styled_df.apply(green_gradient, subset=['Annualized Return %'], vmin=0, vmax=60)

    # Distance to Strike: vmin=0, vmax=20 (blue — farther OTM = safer)
    if 'Distance to Strike %' in display_df.columns:
        styled_df = styled_df.apply(blue_gradient, subset=['Distance to Strike %'], vmin=0, vmax=20)

    # Spread: vmin=0, vmax=1.00 (warning — wider spread = worse)
    if 'Spread' in display_df.columns:
        styled_df = styled_df.apply(warning_gradient, subset=['Spread'], vmin=0, vmax=1.0)

    # IV: vmin=0, vmax=100 (warning — higher IV = more volatile)
    if 'IV' in display_df.columns:
        styled_df = styled_df.apply(warning_gradient, subset=['IV'], vmin=0, vmax=100)

    # Volume vs Open Interest Heatmap (Preserves font scaling!)
    if 'Volume' in display_df.columns and 'Open Interest' in display_df.columns:
        styled_df = styled_df.apply(vol_oi_heatmap, axis=None, subset=['Volume', 'Open Interest'])

    # Rename columns for display
    column_labels = {
        'Strike Display': 'Strike',
        'Distance to Strike %': 'Distance to Strike %',
        'Days to Expiry': 'Days to Expiry',
        'expirationDate': 'Expiration Date',
        'BidPrice': 'Premium (Bid)',
        'MidPrice': 'Mid Price',
        'AskPrice': 'Ask',
        'Spread': 'Bid-Ask Spread',
        'Breakeven Price': 'Breakeven Price',
        'Static Return %': 'Static Return %',
        'Annualized Return %': 'Annualized Return %',
        'Volume': 'Volume',
        'Open Interest': 'Open Interest',
        'IV': 'Implied Volatility (IV)',
    }
    active_labels = {k: v for k, v in column_labels.items() if k in display_df.columns}
    styled_df = styled_df.relabel_index(
        [active_labels.get(c, c) for c in display_df.columns],
        axis=1
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True,
    )

    # ------------------------------------------------------------------
    # STOCK ANALYSIS
    # ------------------------------------------------------------------
    
    st.markdown("### Stock Analysis")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_premium = filtered_df['BidPrice'].mean()
        st.metric("Avg Premium (Bid)", f"${avg_premium:.2f}")

    with col2:
        avg_return = filtered_df['Static Return %'].mean()
        st.metric("Avg Static Return", f"{avg_return:.2f}%")

    with col3:
        max_return = filtered_df['Static Return %'].max()
        st.metric("Best Return", f"{max_return:.2f}%")

    with col4:
        avg_distance = filtered_df['Distance to Strike %'].mean()
        st.metric("Avg Distance to Strike", f"{avg_distance:.2f}%")

    # Safety vs Reward scatter chart
    st.markdown(
        "#### Distance to Strike % (Safety) vs Annualized Return % (Reward)",
        help="The outer ring size represents the Open Interest. The inner solid dot size represents the Volume traded today."
    )

    # Find global max to lock the scale domains together for true ratio representation
    max_vol_oi = float(max(filtered_df['Volume'].max(), filtered_df['Open Interest'].max()))
    domain_max = max(max_vol_oi, 1.0)  # Avoid domain=[0,0]

    base = alt.Chart(filtered_df).encode(
        x=alt.X('Distance to Strike %:Q', title='Distance to Strike % (Safety)', axis=alt.Axis(grid=True)),
        y=alt.Y('Annualized Return %:Q', title='Annualized Return % (Reward)', axis=alt.Axis(grid=True)),
        color=alt.Color('IV:Q', scale=alt.Scale(scheme='oranges')),
        tooltip=['Ticker', 'Strike', 'Distance to Strike %', 'Annualized Return %', 'IV', 'Volume', 'Open Interest']
    )

    oi_ring = base.mark_point(filled=False).encode(
        size=alt.Size('Open Interest:Q', scale=alt.Scale(domain=[0, domain_max], range=[0, 2000]), legend=None)
    )

    volume_dot = base.mark_circle(opacity=0.9).encode(
        size=alt.Size('Volume:Q', scale=alt.Scale(domain=[0, domain_max], range=[0, 2000]), legend=None)
    )

    layered_chart = (oi_ring + volume_dot).properties(
        height=500
    ).interactive()
    
    st.altair_chart(layered_chart, use_container_width=True)


# =============================================================================
# RUN THE APP
# =============================================================================

if __name__ == "__main__":
    main()
