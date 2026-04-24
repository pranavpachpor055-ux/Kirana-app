import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(page_title='Stock Daily Profit', page_icon='📈', layout='centered')

st.title('Stock info + daily profit')
st.caption("Simple: enter tickers + shares, get today's P/L. Data via Yahoo Finance yfinance")

@st.cache_data(ttl=60)
def fetch_quote(ticker: str):
    tkr = yf.Ticker(ticker)
    info = {}
    try:
        info = tkr.fast_info
    except Exception:
        info = {}

    # Try multiple fields because Yahoo responses vary
    last_price = info.get('last_price') or info.get('lastPrice')
    prev_close = info.get('previous_close') or info.get('previousClose')
    last_price = info.get('lastPrice', 0.0)
    # Fallback: 2d history
    if last_price is None or prev_close is None:
        hist = tkr.history(period='2d', interval='1d')
        if hist is not None and len(hist) >= 1:
            if prev_close is None and len(hist) >= 2:
                prev_close = float(hist['Close'].iloc[-2])
            if last_price is None:
                last_price = float(hist['Close'].iloc[-1])
            if prev_close is None:
                prev_close = float(hist['Close'].iloc[-1])

    # Company name
    name = None
    try:
        name = tkr.get_info().get('shortName')
    except Exception:
        name = None

    return {
        'ticker': ticker.upper().strip(),
        'name': name,
        'last_price': float(last_price) if last_price is not None else None,
        'previous_close': float(prev_close) if prev_close is not None else None,
    }

@st.cache_data(ttl=600)
def fetch_line(ticker: str, period='5d'):
    tkr = yf.Ticker(ticker)
    hist = tkr.history(period=period, interval='1h')
    if hist is None or len(hist) == 0:
        hist = tkr.history(period=period, interval='1d')
    if hist is None or len(hist) == 0:
        return None
    out = hist.reset_index()[['Datetime' if 'Datetime' in hist.reset_index().columns else 'Date', 'Close']].copy()
    out.columns = ['time', 'close']
    return out

st.subheader('Portfolio')
st.write('Edit the table (tickers + shares).')

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(
        {'ticker': ['AAPL', 'MSFT'], 'shares': [10, 5]}
    )

portfolio_df = st.data_editor(
    st.session_state.portfolio,
    num_rows='dynamic',
    use_container_width=True,
    column_config={
        'ticker': st.column_config.TextColumn('Ticker'),
        'shares': st.column_config.NumberColumn('Shares', min_value=0.0, step=1.0),
    },
    key='portfolio_editor',
)

# Keep session state updated
st.session_state.portfolio = portfolio_df

run = st.button('Refresh prices')

rows = []

# Auto-refresh once on load, and on button press
if run or True:
    for _, r in portfolio_df.iterrows():
        t = str(r.get('ticker', '')).strip().upper()
        if t == '' or t == 'NAN':
            continue
        sh = r.get('shares', 0)
        try:
            sh = float(sh)
        except Exception:
            sh = 0.0

        q = fetch_quote(t)
        lp = q['last_price']
        pc = q['previous_close']

        if lp is None or pc is None:
            daily_pl = None
            daily_pl_pct = None
            chg = None
            chg_pct = None
        else:
            chg = lp - pc
            chg_pct = (lp / pc - 1.0) if pc != 0 else None
            daily_pl = sh * (lp - pc)
            daily_pl_pct = chg_pct

        rows.append({
            'ticker': q['ticker'],
            'name': q['name'],
            'shares': sh,
            'last_price': lp,
            'previous_close': pc,
            'change_$': chg,
            'change_%': chg_pct,
            'daily_pl_$': daily_pl,
            'daily_pl_%': daily_pl_pct,
        })

result_df = pd.DataFrame(rows)

st.subheader('Today')

if len(result_df) == 0:
    st.info('Add at least one ticker above.')
else:
    total_pl = result_df['daily_pl_$'].dropna().sum() if 'daily_pl_$' in result_df.columns else 0.0
    c1, c2, c3 = st.columns(3)
    c1.metric('Positions', int(len(result_df)))
    c2.metric('Total daily P/L', f"₹{total_pl:,.2f}")

    # Show table
    show_df = result_df.copy()
    if 'change_%' in show_df.columns:
        show_df['change_%'] = show_df['change_%'] * 100
    if 'daily_pl_%' in show_df.columns:
        show_df['daily_pl_%'] = show_df['daily_pl_%'] * 100

    st.dataframe(
        show_df,
        use_container_width=True,
        column_config={
            'last_price': st.column_config.NumberColumn('Last', format='$%.2f'),
            'previous_close': st.column_config.NumberColumn('Prev close', format='$%.2f'),
            'change_$': st.column_config.NumberColumn('Change', format='$%.2f'),
            'change_%': st.column_config.NumberColumn('Change %', format='%.2f%%'),
            'daily_pl_$': st.column_config.NumberColumn('Daily P/L', format='$%.2f'),
            'daily_pl_%': st.column_config.NumberColumn('Daily P/L %', format='%.2f%%'),
        },
    )

st.subheader('Quick chart')
chart_ticker = st.text_input('Chart ticker', value=(rows[0]['ticker'] if len(rows) else 'AAPL'))
period = st.selectbox('Period', ['5d', '1mo', '3mo', '6mo', '1y'], index=0)

line_df = fetch_line(chart_ticker.strip().upper(), period=period)
if line_df is None:
    st.warning('No chart data found for that ticker.')
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=line_df['time'], y=line_df['close'], mode='lines', name=chart_ticker.upper()))
    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title='Price',
        xaxis_title='',
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption('Note: Daily P/L uses previous close -> last price. This is not total profit since purchase.')
