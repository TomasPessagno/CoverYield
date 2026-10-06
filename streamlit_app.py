"""
CoverYield - Covered Call Screener (Streamlit app)
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
import pandas as pd
from datetime import datetime
from streamlit_searchbox import st_searchbox
import altair as alt

from coveryield.data.provider import DataFetchError
from coveryield.data.universe import DEFAULT_UNIVERSE, TICKER_MAP
from coveryield.data.yahoo import YahooFinanceProvider
from coveryield.screening.filters import (
    add_contract_metrics,
    filter_by_goals,
    filter_by_strike_and_return,
    filter_calls,
)
from coveryield.screening.scan import scan_one_ticker, scan_universe
from coveryield.screening.scoring import (
    compute_opportunity_score,
    normalize_weights,
    rank_opportunities,
)

PROVIDER = YahooFinanceProvider()


# =============================================================================
# CONFIGURATION AND PAGE SETUP
# =============================================================================

st.set_page_config(
    page_title="CoverYield",
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

    /* Restore Material icon font — the global rule above otherwise clobbers it,
       making icons (e.g. the expander arrow) render as literal text like
       "keyboard_arrow_right". */
    span[data-testid="stIconMaterial"],
    [data-testid="stExpanderToggleIcon"],
    [class*="material-symbols"],
    [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons' !important;
    }

    /* Header font stack */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Mozilla Headline', 'Zilla Slab', 'Metropolis', 'Inter', serif !important;
        font-weight: 700 !important;
    }

    /* Field labels drawn by field_label(), so every input in a row lines up
       (the searchbox component renders its own, differently sized label) */
    .ts-field-label {
        font-size: 14px;
        line-height: 1.6;
        color: rgb(49, 51, 63);
        margin: 0;
    }

    /* Min / Max captions at the ends of the Table Size slider */
    .ts-slider-end {
        text-align: center;
        font-size: 0.7rem;
        color: #aaa;
        padding-top: 37px;  /* level with the slider track, below its label and value */
    }

    /* Center the Table Size slider's label over the slider */
    .st-key-table_scale_slider [data-testid="stWidgetLabel"] {
        width: 100%;
        justify-content: center;
        position: relative;
    }
    /* Keep its help icon at the far right without pushing the text off-center */
    .st-key-table_scale_slider [data-testid="stWidgetLabel"] > div {
        position: absolute;
        right: 0;
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

# Build display labels: "Name (Stock Ticker)"
TICKER_OPTIONS = [f"{name} ({sym})" for sym, name in TICKER_MAP.items()]

# =============================================================================
# MAIN APP LOGIC
# =============================================================================

def field_label(text: str) -> None:
    """Render a widget label with one shared style, so inputs in a row line up."""
    st.markdown(f"<p class='ts-field-label'>{text}</p>", unsafe_allow_html=True)


def screener_tab():
    """
    Renders the single-ticker covered call screener.
    Orchestrates the Streamlit UI and ETL pipeline for one ticker.
    """

    # --------------------------------------------------------------------------
    # CONFIGURATION - Inline at top of page
    # --------------------------------------------------------------------------

    st.subheader("Configuration")

    cfg_col1, cfg_col2, cfg_col3 = st.columns(3)

    with cfg_col1:
        field_label("Stock Ticker")
        selected_ticker = st_searchbox(
            PROVIDER.search_tickers,
            placeholder="Search any ticker...",
            key="ticker_searchbox",
            clear_on_submit=False,
            style_overrides={"searchbox": {"control": {"minHeight": "40px"}}},
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
        field_label("Min Days to Expiry")
        min_days = st.number_input(
            "Min Days to Expiry",
            min_value=1,  # Lowered min_value slightly to allow 1-DTE strategies if the user desires
            max_value=60,
            value=7,
            key="min_days_input",
            label_visibility="collapsed",
        )

    with cfg_col3:
        field_label("Max Days to Expiry")
        max_days = st.number_input(
            "Max Days to Expiry",
            min_value=14,
            max_value=90,
            value=42,
            key="max_days_input",
            label_visibility="collapsed",
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
            try:
                chain = PROVIDER.fetch_call_chain(ticker)
            except DataFetchError as e:
                st.error(f"Error fetching data for {ticker}: {e}")
                chain = None

        if chain is None or chain.is_empty:
            st.error(
                f"Could not fetch data for ticker '{ticker}'. "
                "Please verify the symbol is valid."
            )
            st.session_state.cached_data = None
            st.stop()

        current_price, open_price, options_df = chain.price, chain.open_price, chain.calls

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
    
    scan_time_html = f"<span style='font-size: 1.1rem; color: #64748b; margin-left: 15px; font-weight: 400;'>Scanned: {scan_time}</span>" if scan_time else ""

    # Transform/filter the data (runs on every rerender so layout changes apply)
    filtered_df = filter_calls(
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
            css_injection + f"\n<div id='sticky-ticker-bar' style='padding: 15px 25px; border-radius: 8px; background-color: rgba(248, 250, 252, 0.95); backdrop-filter: blur(5px); border: 1px solid #e2e8f0; margin-bottom: 15px; display: inline-block; width: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-top: 5px;'>\n<span style='font-size: 1.8rem; font-weight: 700; margin-right: 20px;'>{ticker}</span>\n<span style='font-size: 1.5rem; margin-right: 15px; font-weight: 500;'>${current_price:.2f}</span>\n<span style='font-size: 1.2rem; color: {color}; font-weight: 600;'>{arrow} ${abs(day_change):.2f} ({day_change_pct:+.2f}%) Today</span>{scan_time_html}\n</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            css_injection + f"\n<div id='sticky-ticker-bar' style='padding: 15px 25px; border-radius: 8px; background-color: rgba(248, 250, 252, 0.95); backdrop-filter: blur(5px); border: 1px solid #e2e8f0; margin-bottom: 15px; display: inline-block; width: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-top: 5px;'>\n<span style='font-size: 1.8rem; font-weight: 700; margin-right: 20px;'>{ticker}</span>\n<span style='font-size: 1.5rem; font-weight: 500;'>${current_price:.2f}</span>{scan_time_html}\n</div>",
            unsafe_allow_html=True
        )

    # ------------------------------------------------------------------
    # Prepare display DataFrame (copy so formatting doesn't corrupt data)
    # ------------------------------------------------------------------

    st.markdown("### Filtered Options Chain")
    st.markdown("<p style='text-align: left; font-style: italic; font-size: 0.85rem; color: #888; padding-bottom: 5px; margin-top: -10px; margin-bottom: 10px;'>*Hover over the interrogation (?) icons or the column headers to know more about them.*</p>", unsafe_allow_html=True)

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

    filtered_df = add_contract_metrics(filtered_df, current_price)
    filtered_df = filter_by_strike_and_return(
        filtered_df,
        current_price,
        min_strike_offset,
        max_strike_offset,
        min_static_return,
        min_annualized_return,
    )

    if filtered_df.empty:
        st.warning("No options within this strike range. Try widening the offsets.")
        return

    # Build Strike Display column: "$155.00 ($5.00)"
    filtered_df['Strike Display'] = filtered_df['Strike'].apply(
        lambda s: f"${s:.2f} (${s - current_price:.2f})"
    )

    # Create the specific contract link using the OCC contractSymbol column
    filtered_df['Yahoo Contract'] = "https://finance.yahoo.com/quote/" + filtered_df['contractSymbol']

    # Keep Robinhood routing to the main ticker page since they don't support contract deep-links
    filtered_df['Robinhood'] = "https://robinhood.com/stocks/" + filtered_df['Ticker']
    filtered_df['TradingView'] = "https://www.tradingview.com/symbols/" + filtered_df['Ticker'] + "/"

    display_columns = [
        'Yahoo Contract',
        'Robinhood',
        'TradingView',
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
        display_df['expirationDate'] = display_df['expirationDate'].dt.strftime('%b %d')


    styled_df = display_df.style

    def format_dte_bar(val: float) -> str:
        if pd.isna(val): return ""
        ratio = min(max(val / max_days, 0), 1) if max_days > 0 else 0
        filled = int(ratio * 6)
        # Using a sleek minimalist wireframe track since raw text cannot be individually colored
        return f"{val:.0f}   {'█' * filled}{'─' * (6 - filled)}"

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
            
            # White to even lighter dark gray (148, 163, 184)
            r = (255 - (255 - 148) * ratio).astype(int)
            g = (255 - (255 - 163) * ratio).astype(int)
            b = (255 - (255 - 184) * ratio).astype(int)
            
            # Use strict black text since the background is now solidly light
            text_colors = ['#000' for val in ratio]
            vol_styles = [f'background-color: rgb({r.iloc[i]},{g.iloc[i]},{b.iloc[i]}); color: {text_colors[i]}' for i in range(len(ratio))]
            
            styles['Volume'] = vol_styles
            styles['Open Interest'] = 'background-color: rgb(148, 163, 184); color: #000'
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

    # The physical st.dataframe configuration block automatically handles all column renaming!
    # --- Table zoom slider + compact toggle ---
    _, min_col, mid_col, max_col, check_col = st.columns([3, 0.6, 4, 0.6, 3])
    min_col.markdown("<div class='ts-slider-end'>Min</div>", unsafe_allow_html=True)
    max_col.markdown("<div class='ts-slider-end'>Max</div>", unsafe_allow_html=True)
    with mid_col:
        table_scale_pct = st.slider(
            "Table Size", min_value=60, max_value=140, value=100, step=5,
            format="%d%%", key="table_scale_slider",
            help="If not all columns are visible on your screen, use your browser's zoom: Ctrl + (−) to zoom out, Ctrl + (+) to zoom in. On Mac, use ⌘ instead of Ctrl."
        )
    with check_col:
        st.markdown("<div style='font-size:0.75rem; font-weight:600; color:#555; margin-bottom:2px; margin-top:4px;'>Compact Columns</div>", unsafe_allow_html=True)
        compact_cols = st.checkbox("Compact", value=False, key="compact_cols_toggle", label_visibility="collapsed")
    table_scale = table_scale_pct / 100
    link_width = 50 if compact_cols else None
    col_width = 75 if compact_cols else None

    # CSS zoom had left-alignment issues — transform: scale keeps things centered
    st.markdown(f"""
        <style>
        div[data-testid="stDataFrame"] > div {{
            transform: scale({table_scale});
            transform-origin: top center;
            margin-left: auto;
            margin-right: auto;
        }}
        </style>
    """, unsafe_allow_html=True)

    if compact_cols:
        col_cfg = {
            "Yahoo Contract": st.column_config.LinkColumn(
                "Y", display_text="YC", width=30,
                help="Direct deep-link to the exact OCC options contract chain on Yahoo Finance."
            ),
            "Robinhood": st.column_config.LinkColumn(
                "R", display_text="RH", width=30,
                help="Deep-link directly to the ticker's main trade execution screen on Robinhood."
            ),
            "TradingView": st.column_config.LinkColumn(
                "T", display_text="TV", width=30,
                help="View the ticker's advanced graphing interface and indicators on TradingView."
            ),
            "Strike Display": st.column_config.Column("Strike", width=100, help="The predefined price at which the underlying asset can be bought or sold."),
            "Distance to Strike %": st.column_config.Column("Dist %", width=50, help="The percentage difference between the underlying asset's current market price and the strike price."),
            "Days to Expiry": st.column_config.Column("DTE", width=85, help="The number of calendar days remaining until the contract matures."),
            "expirationDate": st.column_config.Column("Exp", width=55, help="The specific date on which the contract matures and becomes invalid."),
            "BidPrice": st.column_config.Column("Bid", width=50, help="The highest price currently offered by buyers in the market."),
            "MidPrice": st.column_config.Column("Mid", width=50, help="The calculated average between the current Bid and Ask prices."),
            "AskPrice": st.column_config.Column("Ask", width=50, help="The lowest price currently accepted by sellers in the market."),
            "Spread": st.column_config.Column("Spread", width=50, help="The difference between the Ask and Bid prices, serving as an indicator of market liquidity."),
            "Breakeven Price": st.column_config.Column("B/E", width=50, help="The price the underlying asset must reach at expiration for the position to result in a net-zero profit or loss."),
            "Static Return %": st.column_config.Column("Static %", width=50, help="The projected percentage return if the underlying asset's price remains completely unchanged through expiration."),
            "Annualized Return %": st.column_config.Column("Ann %", width=50, help="The return percentage extrapolated over a 12-month period, used to standardize and compare yields across different timeframes."),
            "Volume": st.column_config.Column("Vol", width=40, help="The total number of contracts transacted during the current trading period."),
            "Open Interest": st.column_config.Column("OI", width=40, help="The total number of active, outstanding contracts currently held by market participants."),
            "IV": st.column_config.Column("IV", width=40, help="A quantitative measure representing the market's expectation of future price fluctuations for the underlying asset."),
        }
    else:
        col_cfg = {
            "Yahoo Contract": st.column_config.LinkColumn(
                "Links", display_text="YC",
                help="Direct deep-link to the exact OCC options contract chain on Yahoo Finance."
            ),
            "Robinhood": st.column_config.LinkColumn(
                "Links", display_text="RH",
                help="Deep-link directly to the ticker's main trade execution screen on Robinhood."
            ),
            "TradingView": st.column_config.LinkColumn(
                "Links", display_text="TV",
                help="View the ticker's advanced graphing interface and indicators on TradingView."
            ),
            "Strike Display": st.column_config.Column("Strike", help="The predefined price at which the underlying asset can be bought or sold."),
            "Distance to Strike %": st.column_config.Column("Distance to Strike %", help="The percentage difference between the underlying asset's current market price and the strike price."),
            "Days to Expiry": st.column_config.Column("Days to Expiry", help="The number of calendar days remaining until the contract matures."),
            "expirationDate": st.column_config.Column("Expiration", width="small", help="The specific date on which the contract matures and becomes invalid."),
            "BidPrice": st.column_config.Column("Premium (Bid)", help="The highest price currently offered by buyers in the market."),
            "MidPrice": st.column_config.Column("Mid Price", help="The calculated average between the current Bid and Ask prices."),
            "AskPrice": st.column_config.Column("Ask", help="The lowest price currently accepted by sellers in the market."),
            "Spread": st.column_config.Column("Bid-Ask Spread", help="The difference between the Ask and Bid prices, serving as an indicator of market liquidity."),
            "Breakeven Price": st.column_config.Column("Breakeven Price", help="The price the underlying asset must reach at expiration for the position to result in a net-zero profit or loss."),
            "Static Return %": st.column_config.Column("Static Return %", help="The projected percentage return if the underlying asset's price remains completely unchanged through expiration."),
            "Annualized Return %": st.column_config.Column("Annualized Return %", help="The return percentage extrapolated over a 12-month period, used to standardize and compare yields across different timeframes."),
            "Volume": st.column_config.Column("Volume", help="The total number of contracts transacted during the current trading period."),
            "Open Interest": st.column_config.Column("Open Interest", help="The total number of active, outstanding contracts currently held by market participants."),
            "IV": st.column_config.Column("Implied Volatility (IV)", help="A quantitative measure representing the market's expectation of future price fluctuations for the underlying asset."),
        }

    st.dataframe(
        styled_df,
        height=450,
        use_container_width=True,
        hide_index=True,
        column_config=col_cfg
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
        tooltip=[
            alt.Tooltip('Ticker', title='Ticker'),
            alt.Tooltip('Strike', title='Strike', format='$.2f'),
            alt.Tooltip('Distance to Strike %', format='.2f'),
            alt.Tooltip('Annualized Return %', format='.2f'),
            alt.Tooltip('IV', title='Implied Volatility', format='.2f'),
            alt.Tooltip('Volume', format=',.0f'),
            alt.Tooltip('Open Interest', format=',.0f'),
        ]
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
# CUSTOM ANALYSIS — multi-stock goal-driven opportunity ranker
# =============================================================================
#
# This tab flips the app around: instead of the user picking a ticker, they
# state their GOALS (target return, risk tolerance, universe) and the software
# scans many stocks, scores every covered-call opportunity, and ranks them.
#
# It scans the built-in ~57-ticker universe live; a scheduled background job
# that precomputes the scan is planned.


# The prototype universe = the curated liquid-options tickers we already ship.
CUSTOM_ANALYSIS_UNIVERSE = DEFAULT_UNIVERSE


@st.cache_data(ttl=600, show_spinner=False)
def cached_scan_one_ticker(ticker: str, min_days: int, max_days: int) -> pd.DataFrame:
    """scan_one_ticker cached for 10 min so re-runs and weight tweaks are instant."""
    return scan_one_ticker(ticker, min_days, max_days, provider=PROVIDER)


def score_gradient(series: pd.Series, vmin: float = 0, vmax: float = 100) -> list[str]:
    """White (low) → rich green (high). Matplotlib-free, matches the Screener tab style."""
    styles = []
    for val in series:
        ratio = min(max((val - vmin) / (vmax - vmin), 0), 1) if vmax > vmin else 0
        r = int(255 - (255 - 30) * ratio)
        g = int(255 - (255 - 130) * ratio)
        b = int(255 - (255 - 50) * ratio)
        text_color = '#000' if ratio < 0.6 else '#fff'
        styles.append(f'background-color: rgb({r},{g},{b}); color: {text_color}')
    return styles


def custom_analysis_tab():
    """Renders the goal-driven, multi-stock opportunity ranker."""

    st.markdown(
        "Tell the screener your **goals** and it scans the universe, scores every "
        "covered-call opportunity, and ranks the best matches. "
        "<span style='color:#888; font-style:italic;'>Prototype — live scan of the "
        "built-in liquid-options universe.</span>",
        unsafe_allow_html=True,
    )

    # ---- Goals ----
    st.subheader("Your Goals")
    g1, g2, g3 = st.columns(3)
    with g1:
        min_static = st.slider(
            "Min Return % (this trade)", min_value=0.0, max_value=20.0, value=1.0, step=0.5,
            key="ca_min_return", format="%.1f%%",
            help="The ACTUAL return earned on this trade: premium ÷ stock price over its DTE. "
                 "Real cash, not a projection. This is the primary goal.",
        )
    with g2:
        max_dte = st.slider(
            "Max Days to Expiry", min_value=1, max_value=120, value=45, step=1,
            key="ca_max_dte_sl",
        )
    with g3:
        min_otm = st.slider(
            "Min Distance OTM %", min_value=0.0, max_value=30.0, value=2.0, step=0.5,
            key="ca_min_otm_sl", format="%.1f%%",
            help="How far above today's price the strike must sit.",
        )
    st.caption(
        "Annualized return is shown in the results and feeds the score (capital efficiency), "
        "but you screen on the *actual* return you'll earn — not a projection."
    )

    # ---- Scoring weights (user-adjustable) ----
    with st.expander("Scoring weights (tune the algorithm to your style)", expanded=False):
        st.caption("Weights are normalized automatically. Defaults: 40 / 30 / 15 / 10 / 5.")
        yield_actual_pct = st.slider(
            "Yield make-up: actual return vs annualized rate", 0, 100, 70,
            key="ca_yield_split", format="%d%% actual",
            help="How the Yield score is built. Left = pure annualized rate (favors short-dated weeklies); "
                 "Right = pure actual return (real cash this trade). Default 70% actual.",
        )
        w1, w2, w3, w4, w5 = st.columns(5)
        with w1:
            w_yield = st.slider("Yield", 0, 100, 40, key="ca_w_yield")
        with w2:
            w_assign = st.slider("Assignment Risk", 0, 100, 30, key="ca_w_assign")
        with w3:
            w_liq = st.slider("Liquidity", 0, 100, 15, key="ca_w_liq")
        with w4:
            w_vol = st.slider("Volatility", 0, 100, 10, key="ca_w_vol")
        with w5:
            w_div = st.slider("Dividend", 0, 100, 5, key="ca_w_div")

    u1, u2 = st.columns(2)
    with u1:
        universe_size = st.number_input(
            "Universe size (tickers to scan)", min_value=5, max_value=len(CUSTOM_ANALYSIS_UNIVERSE),
            value=20, step=5, key="ca_universe_num",
            help="Live scanning is slow (~1-2s/ticker). Keep small while prototyping.",
        )
    with u2:
        top_n = st.number_input(
            "Show top N opportunities", min_value=10, max_value=200, value=50, step=10,
            key="ca_top_n_num",
        )

    run = st.button("Find Opportunities", type="primary", key="ca_run_button")

    # Weights are read from the current sliders and applied LIVE on every rerun.
    weights = normalize_weights(
        {'yield': w_yield, 'assign': w_assign, 'liq': w_liq, 'vol': w_vol, 'div': w_div},
        yield_actual_frac=yield_actual_pct / 100.0,
    )

    # The SCAN (slow) only runs on button click. Its raw result is stashed in
    # session state, so the goal filters + weights below re-apply instantly on
    # every widget change — no re-scan needed. (Scan once, filter many.)
    if run:
        tickers = CUSTOM_ANALYSIS_UNIVERSE[:universe_size]
        progress = st.progress(0.0, text="Starting scan...")

        def _update(frac, ticker):
            progress.progress(frac, text=f"Scanning {ticker}... ({int(frac * 100)}%)")

        # Scan a wide DTE window (1-120d) so Max-DTE becomes a live filter too.
        scanned = scan_universe(
            tickers, min_days=1, max_days=120, progress_cb=_update,
            scan_one=cached_scan_one_ticker,
        )
        progress.empty()
        st.session_state.ca_scanned = scanned if not scanned.empty else None
        st.session_state.ca_scanned_count = len(tickers)

    scanned = st.session_state.get('ca_scanned')
    if scanned is None:
        st.info("Set your goals and click **Find Opportunities** to scan the universe.")
        return

    # ---- Filter + score LIVE (re-runs on any widget change, no re-scan) ----
    scanned_count = st.session_state.get('ca_scanned_count', '?')
    filtered = filter_by_goals(scanned, min_static, max_dte, min_otm)

    if filtered.empty:
        st.warning(
            f"Scanned **{scanned_count}** tickers but **nothing matched your filters**. "
            "Adjust the goals above — lower **Min Return %**, raise **Max Days to Expiry**, "
            "or lower **Min Distance OTM %**. Results update live, no need to re-scan."
        )
        return

    scored = rank_opportunities(compute_opportunity_score(filtered, weights), top_n)

    st.success(
        f"Top **{len(scored)}** of **{len(filtered)}** matching opportunities across "
        f"**{scanned_count}** scanned tickers, ranked by Opportunity Score."
    )

    display = scored.copy()
    display['Strike'] = display['Strike'].map(lambda s: f"${s:.2f}")
    display['Price'] = display['Current Price'].map(lambda s: f"${s:.2f}")
    display['Premium'] = display['BidPrice'].map(lambda s: f"${s:.2f}")
    display['Assign %'] = (display['Assignment Prob'].fillna(0) * 100)
    display['Yahoo'] = "https://finance.yahoo.com/quote/" + display['contractSymbol']

    cols = [
        'Opportunity Score', 'Ticker', 'Price', 'Strike', 'Distance to Strike %',
        'Days to Expiry', 'Premium', 'Static Return %', 'Annualized Return %',
        'Assign %', 'IV', 'Open Interest', 'Yahoo',
    ]
    cols = [c for c in cols if c in display.columns]

    st.dataframe(
        display[cols].style.format({
            'Opportunity Score': '{:.0f}',
            'Distance to Strike %': '{:.1f}%',
            'Static Return %': '{:.2f}%',
            'Annualized Return %': '{:.1f}%',
            'Assign %': '{:.0f}%',
            'IV': '{:.0f}%',
        }).apply(score_gradient, subset=['Opportunity Score']),
        height=520, use_container_width=True, hide_index=True,
        column_config={
            'Opportunity Score': st.column_config.Column("Score", help="Weighted 0-100 blend of yield, assignment risk, liquidity, volatility, dividend."),
            'Distance to Strike %': st.column_config.Column("Dist %"),
            'Days to Expiry': st.column_config.Column("DTE"),
            'Static Return %': st.column_config.Column("Yield"),
            'Annualized Return %': st.column_config.Column("Annual."),
            'Assign %': st.column_config.Column("Assign %", help="Approx. probability of assignment (≈ call delta)."),
            'Open Interest': st.column_config.Column("OI"),
            'Yahoo': st.column_config.LinkColumn("Link", display_text="YC"),
        },
    )


# =============================================================================
# RUN THE APP
# =============================================================================

def main():
    """App entry point — renders the title and the two tabs."""
    st.title("CoverYield")
    tab_screener, tab_custom = st.tabs(["Screener", "Custom Analysis"])
    with tab_screener:
        screener_tab()
    with tab_custom:
        custom_analysis_tab()


if __name__ == "__main__":
    main()
