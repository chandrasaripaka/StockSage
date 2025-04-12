import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import threading
import random
import string
from datetime import datetime, timedelta
from stock_analysis import (
    get_stock_data, 
    get_financial_metrics, 
    calculate_moving_averages,
    calculate_rsi,
    calculate_macd,
    get_news
)
from utils import format_large_number, format_percentage

# Import Tiger Trading components
from trading_strategies import STRATEGY_REGISTRY, create_strategy
from db_models import Session, Strategy, Trade, PerformanceMetric, engine
from tiger_client import TigerBrokersClient
from trading_bot import TradingBot

# Initialize global trading bot
trading_bot = None

# Page configuration
st.set_page_config(
    page_title="Stock Analysis Tool",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title and description
st.title("Stock Analysis Tool")
st.markdown("An interactive tool for analyzing stock market data and financial metrics")

# Sidebar for inputs
with st.sidebar:
    st.header("Stock Selection")
    
    # Default popular stocks
    popular_stocks = {
        "Apple": "AAPL",
        "Microsoft": "MSFT", 
        "Amazon": "AMZN",
        "Tesla": "TSLA",
        "Google": "GOOGL",
        "Meta": "META",
        "NVIDIA": "NVDA",
        "Netflix": "NFLX"
    }
    
    # Stock search/selection options
    search_or_select = st.radio(
        "Choose a stock",
        ["Select from popular stocks", "Search by symbol"]
    )
    
    if search_or_select == "Select from popular stocks":
        selected_stock_name = st.selectbox(
            "Select a company",
            list(popular_stocks.keys())
        )
        stock_symbol = popular_stocks[selected_stock_name]
        
    else:
        stock_symbol = st.text_input(
            "Enter stock symbol",
            value="AAPL"
        ).upper()
    
    # Time period selection
    time_periods = {
        "1 Month": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365,
        "2 Years": 730,
        "5 Years": 1825
    }
    
    selected_period = st.selectbox(
        "Select time period",
        list(time_periods.keys()),
        index=3  # Default to 1 Year
    )
    
    days = time_periods[selected_period]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Chart type selection
    chart_type = st.selectbox(
        "Select chart type",
        ["Candlestick", "Line", "OHLC"]
    )
    
    # Technical indicators
    st.header("Technical Indicators")
    show_ma = st.checkbox("Moving Averages", value=True)
    show_rsi = st.checkbox("Relative Strength Index (RSI)", value=False)
    show_macd = st.checkbox("MACD", value=False)
    
    # Date range
    st.header("Date Range")
    st.write(f"From: {start_date.strftime('%Y-%m-%d')}")
    st.write(f"To: {end_date.strftime('%Y-%m-%d')}")
    
    # Refresh button
    if st.button("Refresh Data"):
        st.rerun()

# App tabs
tab1, tab2 = st.tabs(["Stock Analysis", "Algorithmic Trading"])

# Tab 1: Stock Analysis
with tab1:
    # Main content area
    try:
        # Display loading message while fetching data
        with st.spinner(f"Loading data for {stock_symbol}..."):
            # Get stock data
            df = get_stock_data(stock_symbol, start_date, end_date)
            
            if df.empty:
                st.error(f"No data found for {stock_symbol}. Please check the symbol and try again.")
                st.stop()
            
            # Get company info and financial metrics
            ticker = yf.Ticker(stock_symbol)
            info = ticker.info
            
            # Get financial metrics
            financial_metrics = get_financial_metrics(ticker)
            
            # Calculate technical indicators if needed
            if show_ma:
                df = calculate_moving_averages(df, [20, 50, 200])
            
            if show_rsi:
                df = calculate_rsi(df)
                
            if show_macd:
                df = calculate_macd(df)
        
        # Display company header
        col1, col2 = st.columns([3, 1])
        
        with col1:
            company_name = info.get('shortName', stock_symbol)
            st.header(f"{company_name} ({stock_symbol})")
            
            # Current price and daily change
            if 'regularMarketPrice' in info and 'previousClose' in info:
                current_price = info['regularMarketPrice']
                prev_close = info['previousClose']
                price_change = current_price - prev_close
                pct_change = (price_change / prev_close) * 100
                
                price_color = "green" if price_change >= 0 else "red"
                change_icon = "▲" if price_change >= 0 else "▼"
                
                st.markdown(f"""
                <div style="display: flex; align-items: baseline;">
                    <h2 style="margin: 0; padding-right: 10px;">${current_price:.2f}</h2>
                    <h3 style="margin: 0; color: {price_color};">{change_icon} {abs(price_change):.2f} ({pct_change:.2f}%)</h3>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            # Summary metrics
            if 'marketCap' in info:
                st.metric("Market Cap", format_large_number(info.get('marketCap', 0)))
            if 'volume' in info and 'averageVolume' in info:
                vol_pct = ((info.get('volume', 0) / info.get('averageVolume', 1)) - 1) * 100
                st.metric("Volume", format_large_number(info.get('volume', 0)), 
                         f"{format_percentage(vol_pct)} vs avg")
        
        # Price chart section
        st.subheader("Price Chart")
        
        # Create figure for price chart
        fig = go.Figure()
        
        # Add price data based on chart type
        if chart_type == "Candlestick":
            fig.add_trace(
                go.Candlestick(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name="Price"
                )
            )
        elif chart_type == "Line":
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df['Close'],
                    mode='lines',
                    name="Close Price",
                    line=dict(color='#17BECF', width=2)
                )
            )
        elif chart_type == "OHLC":
            fig.add_trace(
                go.Ohlc(
                    x=df.index,
                    open=df['Open'],
                    high=df['High'],
                    low=df['Low'],
                    close=df['Close'],
                    name="Price"
                )
            )
        
        # Add moving averages if selected
        if show_ma:
            for ma in [20, 50, 200]:
                col_name = f'MA_{ma}'
                if col_name in df.columns:
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df[col_name],
                            mode='lines',
                            name=f"{ma}-day MA",
                            line=dict(width=1)
                        )
                    )
        
        # Update layout
        fig.update_layout(
            title=f"{stock_symbol} - {selected_period} Price Chart",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            height=500,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark",
            xaxis_rangeslider_visible=False
        )
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
        
        # Technical indicators in separate charts
        if show_rsi or show_macd:
            st.subheader("Technical Indicators")
            
            indicator_tabs = st.tabs(['RSI', 'MACD'])
            
            # RSI Chart
            with indicator_tabs[0]:
                if show_rsi and 'RSI' in df.columns:
                    rsi_fig = go.Figure()
                    rsi_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['RSI'],
                            mode='lines',
                            name="RSI",
                            line=dict(color='purple', width=2)
                        )
                    )
                    
                    # Add overbought/oversold lines
                    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red", 
                                      annotation_text="Overbought (70)")
                    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green", 
                                     annotation_text="Oversold (30)")
                    
                    rsi_fig.update_layout(
                        title="Relative Strength Index (RSI)",
                        xaxis_title="Date",
                        yaxis_title="RSI Value",
                        height=300,
                        template="plotly_dark",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(rsi_fig, use_container_width=True)
                    
                    st.markdown("""
                    **RSI Interpretation:**
                    - Values above 70 indicate that a stock may be overbought (potential sell signal)
                    - Values below 30 indicate that a stock may be oversold (potential buy signal)
                    - The centerline at 50 can signal trend strength/direction
                    """)
                else:
                    st.info("Enable RSI in the sidebar to view this indicator")
            
            # MACD Chart
            with indicator_tabs[1]:
                if show_macd and 'MACD' in df.columns and 'Signal' in df.columns:
                    macd_fig = go.Figure()
                    macd_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['MACD'],
                            mode='lines',
                            name="MACD",
                            line=dict(color='#17BECF', width=2)
                        )
                    )
                    macd_fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=df['Signal'],
                            mode='lines',
                            name="Signal",
                            line=dict(color='orange', width=1.5)
                        )
                    )
                    
                    # Add MACD histogram
                    colors = ['green' if val >= 0 else 'red' for val in (df['MACD'] - df['Signal'])]
                    macd_fig.add_trace(
                        go.Bar(
                            x=df.index,
                            y=df['MACD'] - df['Signal'],
                            name="Histogram",
                            marker_color=colors,
                            opacity=0.5
                        )
                    )
                    
                    macd_fig.update_layout(
                        title="Moving Average Convergence Divergence (MACD)",
                        xaxis_title="Date",
                        yaxis_title="MACD Value",
                        height=300,
                        template="plotly_dark",
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(macd_fig, use_container_width=True)
                    
                    st.markdown("""
                    **MACD Interpretation:**
                    - When MACD crosses above the signal line: Bullish signal
                    - When MACD crosses below the signal line: Bearish signal
                    - Histogram shows momentum (distance between MACD and signal)
                    - MACD crossing above/below zero line can indicate trend changes
                    """)
                else:
                    st.info("Enable MACD in the sidebar to view this indicator")
        
        # Financial metrics section
        st.subheader("Financial Metrics")
        
        metrics_cols = st.columns(4)
        
        with metrics_cols[0]:
            st.metric("P/E Ratio", financial_metrics.get('PE Ratio', 'N/A'))
            st.metric("Dividend Yield", financial_metrics.get('Dividend Yield', 'N/A'))
            
        with metrics_cols[1]:
            st.metric("EPS", financial_metrics.get('EPS', 'N/A'))
            st.metric("Forward P/E", financial_metrics.get('Forward P/E', 'N/A'))
            
        with metrics_cols[2]:
            st.metric("52W High", financial_metrics.get('52 Week High', 'N/A'))
            st.metric("Beta", financial_metrics.get('Beta', 'N/A'))
            
        with metrics_cols[3]:
            st.metric("52W Low", financial_metrics.get('52 Week Low', 'N/A'))
            st.metric("PEG Ratio", financial_metrics.get('PEG Ratio', 'N/A'))
        
        # Company information
        with st.expander("Company Information"):
            if 'longBusinessSummary' in info:
                st.markdown(info['longBusinessSummary'])
            else:
                st.info("No company description available")
        
        # News section
        st.subheader("Recent News")
        news = get_news(ticker)
        
        if news:
            for article in news[:5]:  # Display up to 5 news articles
                st.markdown(f"### [{article['title']}]({article['link']})")
                st.markdown(f"**Source:** {article.get('source', 'Unknown')} | **Published:** {article.get('publishedDate', 'Unknown date')}")
                if 'summary' in article:
                    st.markdown(article['summary'])
                st.markdown("---")
        else:
            st.info("No recent news available")
        
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.info("Please check the stock symbol and try again. If the issue persists, the data source may be temporarily unavailable.")

# Tab 2: Algorithmic Trading
with tab2:
    st.header("Algorithmic Trading")
    st.markdown("Connect to Tiger Brokers API and set up automated trading strategies")
    
    # Tiger Brokers API Credentials setup
    api_config_expander = st.expander("Tiger Brokers API Credentials", expanded=not os.environ.get('TIGER_ID'))
    
    with api_config_expander:
        st.markdown("""
        ### Tiger Brokers API Setup
        To use algorithmic trading features, you need to configure your Tiger Brokers API credentials.
        These are used to connect to your paper trading account.
        """)
        
        # Create columns for API inputs
        col1, col2 = st.columns(2)
        
        with col1:
            # Show current status of API credentials
            st.subheader("API Credentials Status")
            
            tiger_id_status = "✅ Configured" if os.environ.get('TIGER_ID') else "❌ Not Configured"
            st.markdown(f"**Tiger ID:** {tiger_id_status}")
            
            tiger_key_status = "✅ Configured" if os.environ.get('TIGER_PRIVATE_KEY') and len(os.environ.get('TIGER_PRIVATE_KEY', '')) > 10 else "❌ Not Configured"
            st.markdown(f"**Private Key:** {tiger_key_status}")
            
            tiger_pwd_status = "✅ Configured" if os.environ.get('TIGER_PRIVATE_KEY_PASSWORD') else "❌ Not Configured"
            st.markdown(f"**Private Key Password:** {tiger_pwd_status}")
            
            # Use mock client option
            st.subheader("Demo Mode")
            use_mock = st.checkbox("Use demo mode (simulated trading)", value=os.environ.get('USE_MOCK_TIGER', 'true').lower() == 'true')
            if use_mock:
                st.info("Using simulated paper trading. No real API credentials required.")
                # Set environment variable for mock client
                os.environ['USE_MOCK_TIGER'] = 'true'
            else:
                os.environ['USE_MOCK_TIGER'] = 'false'
                
        with col2:
            st.subheader("Configure API Credentials")
            
            # Tiger ID input
            tiger_id = st.text_input("Tiger ID", value=os.environ.get('TIGER_ID', ''), type="default")
            
            # Private Key Password input
            tiger_pwd = st.text_input("Private Key Password", value=os.environ.get('TIGER_PRIVATE_KEY_PASSWORD', ''), type="password")
            
            # Private Key file upload (PEM format)
            st.markdown("**Private Key File (PEM format)**")
            uploaded_file = st.file_uploader("Upload your private key file", type=['pem', 'txt'])
            
            if uploaded_file is not None:
                private_key = uploaded_file.getvalue().decode('utf-8')
                # Save to environment variable
                os.environ['TIGER_PRIVATE_KEY'] = private_key
                # Also save to file
                with open('tiger_private_key.pem', 'w') as f:
                    f.write(private_key)
                st.success("Private key file uploaded successfully!")
            
            # Save button for Tiger ID and password
            if st.button("Save Credentials"):
                if tiger_id:
                    os.environ['TIGER_ID'] = tiger_id
                if tiger_pwd:
                    os.environ['TIGER_PRIVATE_KEY_PASSWORD'] = tiger_pwd
                st.success("Credentials saved!")
                st.rerun()
    
    # Check for API credentials or mock mode
    tiger_credentials = use_mock or all([
        os.environ.get('TIGER_ID'),
        os.environ.get('TIGER_PRIVATE_KEY_PASSWORD')
    ])
    
    if not tiger_credentials:
        st.warning("Tiger Brokers API credentials are not configured and demo mode is disabled. Please set up your credentials or enable demo mode to continue.")
    else:
        # Try to connect to Tiger Brokers API
        if trading_bot is None:
            st.info("Initializing connection to Tiger Brokers...")
            trading_bot = TradingBot()
        
        # Connection status
        conn_col1, conn_col2 = st.columns([3, 1])
        
        with conn_col1:
            if trading_bot and trading_bot.connect():
                st.success("Connected to Tiger Brokers API")
            else:
                st.error("Failed to connect to Tiger Brokers API. Please check your credentials.")
                st.stop()
        
        with conn_col2:
            if st.button("Refresh Connection"):
                trading_bot = None
                st.rerun()
        
        # Trading interface tabs
        algo_tabs = st.tabs(["Strategies", "Account", "Trades", "Performance", "Logs"])
        
        # Strategies tab
        with algo_tabs[0]:
            st.subheader("Trading Strategies")
            
            # Existing strategies
            strategy_session = Session(bind=engine)  # Explicitly bind session to engine
            strategies = strategy_session.query(Strategy).all()
            
            if strategies:
                st.write("Active Strategies:")
                for strategy in strategies:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"**{strategy.name}** ({strategy.symbol}, {strategy.timeframe})")
                    with col2:
                        st.write(f"Type: {strategy.strategy_type}")
                    with col3:
                        if st.button("Delete", key=f"del_{strategy.id}"):
                            strategy_session.delete(strategy)
                            strategy_session.commit()
                            st.rerun()
                    
                    # Display parameters
                    with st.expander("Parameters"):
                        params = json.loads(strategy.parameters)
                        for param, value in params.items():
                            st.write(f"{param}: {value}")
            else:
                st.info("No trading strategies configured yet. Add a new strategy below.")
            
            strategy_session.close()
            
            # Add new strategy
            st.subheader("Create New Strategy")
            
            col1, col2 = st.columns(2)
            
            with col1:
                strategy_name = st.text_input("Strategy Name", placeholder="MA Crossover AAPL")
                strategy_symbol = st.text_input("Stock Symbol", value=stock_symbol)
                
                timeframe_options = {
                    "1 Day": "1d",
                    "1 Hour": "1h",
                    "5 Minutes": "5m",
                    "1 Minute": "1m"
                }
                strategy_timeframe = st.selectbox(
                    "Timeframe",
                    options=list(timeframe_options.keys())
                )
                
                strategy_type = st.selectbox(
                    "Strategy Type",
                    options=list(STRATEGY_REGISTRY.keys()),
                    format_func=lambda x: x.replace("_", " ").title()
                )
            
            with col2:
                # Dynamic parameters based on strategy type
                st.subheader("Strategy Parameters")
                
                params = {}
                
                if strategy_type == "moving_average_crossover":
                    params["fast_period"] = st.number_input("Fast MA Period", value=20, min_value=1)
                    params["slow_period"] = st.number_input("Slow MA Period", value=50, min_value=1)
                    params["ma_type"] = st.selectbox(
                        "Moving Average Type",
                        options=["simple", "exponential"],
                        format_func=lambda x: "Simple" if x == "simple" else "Exponential"
                    )
                    params["signal_mode"] = st.selectbox(
                        "Signal Mode",
                        options=["crossover", "continuous"],
                        format_func=lambda x: "Crossover Only" if x == "crossover" else "Continuous",
                        help="Crossover mode generates signals only at crossover points. Continuous mode generates signals as long as conditions are met."
                    )
                
                elif strategy_type == "rsi":
                    params["rsi_period"] = st.number_input("RSI Period", value=14, min_value=1)
                    params["oversold"] = st.number_input("Oversold Level", value=30, min_value=1, max_value=100)
                    params["overbought"] = st.number_input("Overbought Level", value=70, min_value=1, max_value=100)
                
                elif strategy_type == "macd":
                    params["fast_period"] = st.number_input("Fast EMA Period", value=12, min_value=1)
                    params["slow_period"] = st.number_input("Slow EMA Period", value=26, min_value=1)
                    params["signal_period"] = st.number_input("Signal Period", value=9, min_value=1)
                
                elif strategy_type == "custom":
                    # Custom strategy builder
                    st.write("This is the custom strategy builder where you can combine multiple indicators and conditions.")
                    
                    # Custom strategy interface in tabs
                    builder_tabs = st.tabs(["Indicators", "Buy Conditions", "Sell Conditions"])
                    
                    # Indicators selection
                    with builder_tabs[0]:
                        st.subheader("Select Technical Indicators")
                        
                        # Initialize indicators list
                        if 'strategy_indicators' not in st.session_state:
                            st.session_state.strategy_indicators = []
                        
                        # Add indicator form
                        indicator_type = st.selectbox(
                            "Indicator Type",
                            options=["SMA", "EMA", "RSI", "MACD", "Bollinger Bands", "Price Channel"],
                            key="indicator_type"
                        )
                        
                        # Dynamic parameters based on indicator type
                        indicator_params = {}
                        
                        if indicator_type == "SMA":
                            period = st.number_input("Period", value=20, min_value=1, key="sma_period")
                            indicator_params = {"type": "sma", "period": int(period)}
                            display_name = f"SMA ({period})"
                        
                        elif indicator_type == "EMA":
                            period = st.number_input("Period", value=20, min_value=1, key="ema_period")
                            indicator_params = {"type": "ema", "period": int(period)}
                            display_name = f"EMA ({period})"
                        
                        elif indicator_type == "RSI":
                            period = st.number_input("Period", value=14, min_value=1, key="rsi_period")
                            indicator_params = {"type": "rsi", "period": int(period)}
                            display_name = f"RSI ({period})"
                        
                        elif indicator_type == "MACD":
                            fast = st.number_input("Fast Period", value=12, min_value=1, key="macd_fast")
                            slow = st.number_input("Slow Period", value=26, min_value=1, key="macd_slow")
                            signal = st.number_input("Signal Period", value=9, min_value=1, key="macd_signal")
                            indicator_params = {
                                "type": "macd", 
                                "fast_period": int(fast), 
                                "slow_period": int(slow),
                                "signal_period": int(signal)
                            }
                            display_name = f"MACD ({fast}, {slow}, {signal})"
                        
                        elif indicator_type == "Bollinger Bands":
                            period = st.number_input("Period", value=20, min_value=1, key="bb_period")
                            std_dev = st.number_input("Standard Deviations", value=2.0, min_value=0.1, key="bb_std")
                            indicator_params = {"type": "bollinger_bands", "period": int(period), "std_dev": float(std_dev)}
                            display_name = f"Bollinger Bands ({period}, {std_dev})"
                        
                        elif indicator_type == "Price Channel":
                            period = st.number_input("Period", value=20, min_value=1, key="pc_period")
                            indicator_params = {"type": "price_channel", "period": int(period)}
                            display_name = f"Price Channel ({period})"
                        
                        # Button to add indicator
                        if st.button("Add Indicator"):
                            indicator_params["display_name"] = display_name
                            st.session_state.strategy_indicators.append(indicator_params)
                            st.success(f"Added {display_name} to strategy")
                        
                        # Display selected indicators
                        if st.session_state.strategy_indicators:
                            st.subheader("Selected Indicators")
                            for i, indicator in enumerate(st.session_state.strategy_indicators):
                                col1, col2 = st.columns([3, 1])
                                with col1:
                                    st.write(f"{i+1}. {indicator['display_name']}")
                                with col2:
                                    if st.button("Remove", key=f"remove_indicator_{i}"):
                                        st.session_state.strategy_indicators.pop(i)
                                        st.rerun()
                        else:
                            st.info("No indicators added yet. Add at least one indicator.")
                    
                    # Buy conditions setup
                    with builder_tabs[1]:
                        st.subheader("Define Buy Conditions")
                        
                        # Initialize buy conditions list
                        if 'strategy_buy_conditions' not in st.session_state:
                            st.session_state.strategy_buy_conditions = []
                        
                        # Only allow adding conditions if we have indicators
                        if not st.session_state.strategy_indicators:
                            st.warning("Please add indicators first in the Indicators tab")
                        else:
                            # Get all available indicators
                            available_indicators = []
                            for indicator in st.session_state.strategy_indicators:
                                ind_type = indicator["type"]
                                
                                if ind_type == "sma":
                                    available_indicators.append(f"sma_{indicator['period']}")
                                elif ind_type == "ema":
                                    available_indicators.append(f"ema_{indicator['period']}")
                                elif ind_type == "rsi":
                                    available_indicators.append("rsi")
                                elif ind_type == "macd":
                                    available_indicators.extend(["macd", "macd_signal", "macd_hist"])
                                elif ind_type == "bollinger_bands":
                                    available_indicators.extend(["bb_upper", "bb_middle", "bb_lower"])
                                elif ind_type == "price_channel":
                                    available_indicators.extend(["pc_high", "pc_middle", "pc_low"])
                            
                            # Add price as an option
                            available_indicators = ["price"] + available_indicators
                            
                            # Buy condition form
                            st.write("When:")
                            indicator1 = st.selectbox("", options=available_indicators, key="buy_indicator1")
                            
                            operator = st.selectbox("", 
                                options=[">", "<", "=", "crosses above", "crosses below"],
                                format_func=lambda x: x.replace("crosses above", "crosses above").replace("crosses below", "crosses below"),
                                key="buy_operator"
                            )
                            
                            # For the second indicator, also allow numerical values
                            indicator2_type = st.radio("Compare with:", ["Indicator", "Value"], key="buy_indicator2_type")
                            
                            if indicator2_type == "Indicator":
                                indicator2 = st.selectbox("", options=available_indicators, key="buy_indicator2")
                            else:  # Value
                                indicator2 = st.number_input("Value", key="buy_value")
                            
                            # Translate UI operator to internal operator
                            op_map = {
                                ">": ">",
                                "<": "<",
                                "=": "=",
                                "crosses above": "crosses_above",
                                "crosses below": "crosses_below"
                            }
                            
                            # Button to add condition
                            if st.button("Add Buy Condition"):
                                condition = {
                                    "indicator1": indicator1,
                                    "operator": op_map[operator],
                                    "indicator2": str(indicator2)
                                }
                                
                                # Format for display
                                if indicator2_type == "Value":
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                else:
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                
                                condition["display"] = display_condition
                                st.session_state.strategy_buy_conditions.append(condition)
                                st.success(f"Added buy condition: {display_condition}")
                                
                            # Display added conditions
                            if st.session_state.strategy_buy_conditions:
                                st.subheader("Defined Buy Conditions")
                                for i, condition in enumerate(st.session_state.strategy_buy_conditions):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(f"{i+1}. {condition['display']}")
                                    with col2:
                                        if st.button("Remove", key=f"remove_buy_condition_{i}"):
                                            st.session_state.strategy_buy_conditions.pop(i)
                                            st.rerun()
                            else:
                                st.info("No buy conditions added yet.")
                    
                    # Sell conditions setup
                    with builder_tabs[2]:
                        st.subheader("Define Sell Conditions")
                        
                        # Initialize sell conditions list
                        if 'strategy_sell_conditions' not in st.session_state:
                            st.session_state.strategy_sell_conditions = []
                        
                        # Only allow adding conditions if we have indicators
                        if not st.session_state.strategy_indicators:
                            st.warning("Please add indicators first in the Indicators tab")
                        else:
                            # Get all available indicators (same as buy conditions)
                            available_indicators = []
                            for indicator in st.session_state.strategy_indicators:
                                ind_type = indicator["type"]
                                
                                if ind_type == "sma":
                                    available_indicators.append(f"sma_{indicator['period']}")
                                elif ind_type == "ema":
                                    available_indicators.append(f"ema_{indicator['period']}")
                                elif ind_type == "rsi":
                                    available_indicators.append("rsi")
                                elif ind_type == "macd":
                                    available_indicators.extend(["macd", "macd_signal", "macd_hist"])
                                elif ind_type == "bollinger_bands":
                                    available_indicators.extend(["bb_upper", "bb_middle", "bb_lower"])
                                elif ind_type == "price_channel":
                                    available_indicators.extend(["pc_high", "pc_middle", "pc_low"])
                            
                            # Add price as an option
                            available_indicators = ["price"] + available_indicators
                            
                            # Sell condition form
                            st.write("When:")
                            indicator1 = st.selectbox("", options=available_indicators, key="sell_indicator1")
                            
                            operator = st.selectbox("", 
                                options=[">", "<", "=", "crosses above", "crosses below"],
                                format_func=lambda x: x.replace("crosses above", "crosses above").replace("crosses below", "crosses below"),
                                key="sell_operator"
                            )
                            
                            # For the second indicator, also allow numerical values
                            indicator2_type = st.radio("Compare with:", ["Indicator", "Value"], key="sell_indicator2_type")
                            
                            if indicator2_type == "Indicator":
                                indicator2 = st.selectbox("", options=available_indicators, key="sell_indicator2")
                            else:  # Value
                                indicator2 = st.number_input("Value", key="sell_value")
                            
                            # Translate UI operator to internal operator
                            op_map = {
                                ">": ">",
                                "<": "<",
                                "=": "=",
                                "crosses above": "crosses_above",
                                "crosses below": "crosses_below"
                            }
                            
                            # Button to add condition
                            if st.button("Add Sell Condition"):
                                condition = {
                                    "indicator1": indicator1,
                                    "operator": op_map[operator],
                                    "indicator2": str(indicator2)
                                }
                                
                                # Format for display
                                if indicator2_type == "Value":
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                else:
                                    display_condition = f"{indicator1} {operator} {indicator2}"
                                
                                condition["display"] = display_condition
                                st.session_state.strategy_sell_conditions.append(condition)
                                st.success(f"Added sell condition: {display_condition}")
                                
                            # Display added conditions
                            if st.session_state.strategy_sell_conditions:
                                st.subheader("Defined Sell Conditions")
                                for i, condition in enumerate(st.session_state.strategy_sell_conditions):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(f"{i+1}. {condition['display']}")
                                    with col2:
                                        if st.button("Remove", key=f"remove_sell_condition_{i}"):
                                            st.session_state.strategy_sell_conditions.pop(i)
                                            st.rerun()
                            else:
                                st.info("No sell conditions added yet.")
                    
                    # Add parameters for custom strategy
                    if 'strategy_indicators' in st.session_state:
                        params["indicators"] = st.session_state.strategy_indicators
                    else:
                        params["indicators"] = []
                        
                    if 'strategy_buy_conditions' in st.session_state:
                        params["buy_conditions"] = st.session_state.strategy_buy_conditions
                    else:
                        params["buy_conditions"] = []
                        
                    if 'strategy_sell_conditions' in st.session_state:
                        params["sell_conditions"] = st.session_state.strategy_sell_conditions
                    else:
                        params["sell_conditions"] = []
            
            if st.button("Create Strategy"):
                if not strategy_name or not strategy_symbol:
                    st.error("Strategy name and symbol are required.")
                else:
                    try:
                        # Add strategy to database
                        strategy_id = trading_bot.add_strategy(
                            strategy_type,
                            strategy_name,
                            strategy_symbol,
                            timeframe_options[strategy_timeframe],
                            **params
                        )
                        
                        if strategy_id:
                            st.success(f"Strategy '{strategy_name}' created successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to create strategy.")
                    except Exception as e:
                        st.error(f"Error creating strategy: {str(e)}")
            
            # Start/Stop Trading Bot
            st.subheader("Trading Bot Control")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Start Trading Bot"):
                    if trading_bot.start_in_thread():
                        st.success("Trading bot started successfully!")
                    else:
                        st.error("Failed to start trading bot.")
            
            with col2:
                if st.button("Stop Trading Bot"):
                    if trading_bot:
                        trading_bot.stop()
                        st.success("Trading bot stopped.")
        
        # Account tab
        with algo_tabs[1]:
            st.subheader("Account Information")
            
            if trading_bot and trading_bot.tiger_client:
                try:
                    # Get account summary
                    account_summary = trading_bot.tiger_client.get_account_summary()
                    
                    # Display account metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Cash Balance", f"${account_summary.cash:.2f}")
                        st.metric("Buying Power", f"${account_summary.buying_power:.2f}")
                    
                    with col2:
                        st.metric("Net Liquidation", f"${account_summary.net_liquidation:.2f}")
                        st.metric("Initial Margin", f"${account_summary.initial_margin_requirement:.2f}")
                    
                    with col3:
                        st.metric("Maintenance Margin", f"${account_summary.maintenance_margin_requirement:.2f}")
                        st.metric("Available Funds", f"${account_summary.available_funds:.2f}")
                    
                    # Get current positions
                    positions = trading_bot.tiger_client.get_positions()
                    
                    if positions:
                        st.subheader("Current Positions")
                        
                        # Create DataFrame for positions
                        position_data = []
                        for pos in positions:
                            position_data.append({
                                "Symbol": pos.symbol,
                                "Quantity": pos.quantity,
                                "Average Cost": f"${pos.average_cost:.2f}",
                                "Market Value": f"${pos.market_value:.2f}",
                                "Unrealized P/L": f"${pos.unrealized_pnl:.2f}",
                                "Unrealized P/L %": f"{pos.unrealized_pnl_percent:.2f}%"
                            })
                        
                        if position_data:
                            position_df = pd.DataFrame(position_data)
                            st.dataframe(position_df)
                        else:
                            st.info("No open positions.")
                    else:
                        st.info("No open positions.")
                    
                    # Recent orders
                    orders = trading_bot.tiger_client.get_order_history()
                    
                    if orders:
                        st.subheader("Recent Orders")
                        
                        # Create DataFrame for orders
                        order_data = []
                        for order in orders[:10]:  # Show 10 most recent orders
                            order_data.append({
                                "Order ID": order.order_id,
                                "Symbol": order.symbol,
                                "Action": order.action,
                                "Quantity": order.quantity,
                                "Order Type": order.order_type,
                                "Limit Price": f"${order.limit_price:.2f}" if order.limit_price else "N/A",
                                "Status": order.status,
                                "Time": order.create_time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                        
                        if order_data:
                            order_df = pd.DataFrame(order_data)
                            st.dataframe(order_df)
                        else:
                            st.info("No recent orders.")
                    else:
                        st.info("No recent orders.")
                
                except Exception as e:
                    st.error(f"Error fetching account information: {str(e)}")
        
        # Performance tab
        # Trades tab
        with algo_tabs[2]:
            st.subheader("Trading Activity")
            
            # Get trades from database
            trades_session = Session(bind=engine)  # Explicitly bind session to engine
            trades = trades_session.query(Trade).order_by(Trade.timestamp.desc()).all()
            
            # Filter options
            col1, col2, col3 = st.columns(3)
            with col1:
                filter_symbol = st.text_input("Filter by Symbol", placeholder="e.g., AAPL")
            with col2:
                filter_direction = st.selectbox("Filter by Direction", options=["All", "BUY", "SELL"], index=0)
            with col3:
                filter_status = st.selectbox("Filter by Status", options=["All", "PENDING", "FILLED", "CANCELLED", "REJECTED"], index=0)
            
            # Apply filters
            filtered_trades = []
            for trade in trades:
                if filter_symbol and filter_symbol.upper() != trade.symbol.upper():
                    continue
                if filter_direction != "All" and filter_direction != trade.direction:
                    continue
                if filter_status != "All" and filter_status != trade.status:
                    continue
                
                # Get strategy name
                strategy_name = "Unknown"
                if trade.strategy_id is not None:
                    strategy = trades_session.query(Strategy).filter_by(id=trade.strategy_id).first()
                    if strategy:
                        strategy_name = strategy.name
                
                # Calculate holding period for closed trades
                holding_period = ""
                if trade.exit_timestamp and trade.timestamp:
                    delta = trade.exit_timestamp - trade.timestamp
                    days = delta.days
                    hours, remainder = divmod(delta.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    if days > 0:
                        holding_period = f"{days}d {hours}h"
                    elif hours > 0:
                        holding_period = f"{hours}h {minutes}m"
                    else:
                        holding_period = f"{minutes}m"
                
                # Format profit/loss
                pl_color = ""
                pl_display = ""
                if trade.profit_loss is not None:
                    pl_color = "green" if trade.profit_loss > 0 else ("red" if trade.profit_loss < 0 else "")
                    pl_display = f"${trade.profit_loss:.2f} ({trade.profit_loss_percent:.2f}%)" if trade.profit_loss_percent is not None else f"${trade.profit_loss:.2f}"
                
                filtered_trades.append({
                    "ID": trade.id,
                    "Strategy": strategy_name,
                    "Symbol": trade.symbol,
                    "Action": trade.direction,
                    "Quantity": trade.quantity,
                    "Entry Price": f"${trade.price:.2f}" if trade.price else "",
                    "Exit Price": f"${trade.exit_price:.2f}" if trade.exit_price else "",
                    "P/L": pl_display,
                    "Status": trade.status,
                    "Entry Time": trade.timestamp.strftime("%Y-%m-%d %H:%M") if trade.timestamp else "",
                    "Exit Time": trade.exit_timestamp.strftime("%Y-%m-%d %H:%M") if trade.exit_timestamp else "",
                    "Holding Period": holding_period,
                    "Order ID": trade.order_id,
                    "pl_color": pl_color  # For highlighting
                })
            
            trades_session.close()
            
            # Display trades
            if filtered_trades:
                st.write(f"Showing {len(filtered_trades)} trades")
                
                # Convert to DataFrame for display
                trades_df = pd.DataFrame(filtered_trades)
                display_cols = [col for col in trades_df.columns if col != "pl_color"]
                
                # Display dataframe
                st.dataframe(trades_df[display_cols], use_container_width=True)
                
                # Trading activity summary
                st.subheader("Trading Summary")
                total_trades = len(filtered_trades)
                
                # Calculate winning and losing trades
                winning_trades = sum(1 for t in filtered_trades if t["pl_color"] == "green")
                losing_trades = sum(1 for t in filtered_trades if t["pl_color"] == "red")
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                # Display metrics
                metric_cols = st.columns(4)
                with metric_cols[0]:
                    st.metric("Total Trades", total_trades)
                with metric_cols[1]:
                    st.metric("Winning Trades", winning_trades)
                with metric_cols[2]:
                    st.metric("Losing Trades", losing_trades) 
                with metric_cols[3]:
                    st.metric("Win Rate", f"{win_rate:.1f}%")
            else:
                st.info("No trades found with the selected filters.")
                
                # Add a demo trade button for testing
                if st.button("Generate Demo Trade"):
                    # Create a new session
                    session = Session(bind=engine)
                    try:
                        # Get a random active strategy
                        strategy = session.query(Strategy).first()
                        
                        if strategy:
                            # Create a demo trade
                            now = datetime.now()
                            
                            # Random trade details
                            direction = "BUY" if random.random() > 0.5 else "SELL"
                            price = round(random.uniform(100, 200), 2)
                            quantity = random.randint(1, 20)
                            order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
                            
                            # Create trade object
                            trade = Trade(
                                strategy_id=strategy.id,
                                order_id=order_id,
                                symbol=strategy.symbol,
                                direction=direction,
                                quantity=quantity,
                                price=price,
                                timestamp=now,
                                status="FILLED"
                            )
                            
                            # Add to database
                            session.add(trade)
                            session.commit()
                            st.success(f"Created demo {direction} trade for {quantity} shares of {strategy.symbol} at ${price:.2f}")
                            st.rerun()
                        else:
                            st.error("No strategies found. Please create a strategy first.")
                    except Exception as e:
                        st.error(f"Error creating demo trade: {str(e)}")
                    finally:
                        session.close()
        
        # Performance tab
        with algo_tabs[3]:
            st.subheader("Strategy Performance")
            
            # Get performance metrics from database
            performance_session = Session(bind=engine)
            metrics = performance_session.query(
                Strategy.name,
                Strategy.symbol,
                Strategy.strategy_type,
                PerformanceMetric.total_trades,
                PerformanceMetric.win_rate,
                PerformanceMetric.total_return,
                PerformanceMetric.start_date,
                PerformanceMetric.end_date
            ).join(
                PerformanceMetric, 
                Strategy.id == PerformanceMetric.strategy_id
            ).all()
            
            if metrics:
                # Convert to DataFrame for display
                metrics_data = []
                for m in metrics:
                    metrics_data.append({
                        "Strategy": m.name,
                        "Symbol": m.symbol,
                        "Type": m.strategy_type,
                        "Total Trades": m.total_trades,
                        "Win Rate": f"{m.win_rate*100:.2f}%" if m.win_rate else "N/A",
                        "Total Return": f"${m.total_return:.2f}" if m.total_return else "N/A",
                        "Period": f"{m.start_date.strftime('%Y-%m-%d')} to {m.end_date.strftime('%Y-%m-%d')}"
                    })
                
                metrics_df = pd.DataFrame(metrics_data)
                st.dataframe(metrics_df)
                
                # Visualize performance
                if st.checkbox("Show Performance Chart"):
                    # Get strategy for chart
                    strategy_names = [m.name for m in metrics]
                    selected_strategy = st.selectbox("Select Strategy", strategy_names)
                    
                    # Get trade history for selected strategy
                    strategy_id = performance_session.query(Strategy.id).filter_by(name=selected_strategy).scalar()
                    
                    if strategy_id:
                        trades = performance_session.query(Trade).filter_by(
                            strategy_id=strategy_id, 
                            status="FILLED",
                            exit_price=Trade.exit_price.isnot(None)
                        ).order_by(Trade.timestamp).all()
                        
                        if trades:
                            # Prepare data for chart
                            trade_data = []
                            cumulative_return = 0
                            
                            for trade in trades:
                                profit_loss = trade.profit_loss or 0
                                cumulative_return += profit_loss
                                
                                trade_data.append({
                                    "date": trade.timestamp,
                                    "profit_loss": profit_loss,
                                    "cumulative_return": cumulative_return
                                })
                            
                            if trade_data:
                                trade_df = pd.DataFrame(trade_data)
                                
                                # Create performance chart
                                fig = go.Figure()
                                
                                # Cumulative return line
                                fig.add_trace(
                                    go.Scatter(
                                        x=trade_df["date"],
                                        y=trade_df["cumulative_return"],
                                        mode="lines",
                                        name="Cumulative Return",
                                        line=dict(color="#0ABAB5", width=2)
                                    )
                                )
                                
                                # Individual trade bars
                                colors = ["green" if pl >= 0 else "red" for pl in trade_df["profit_loss"]]
                                fig.add_trace(
                                    go.Bar(
                                        x=trade_df["date"],
                                        y=trade_df["profit_loss"],
                                        name="Trade P/L",
                                        marker_color=colors,
                                        opacity=0.6
                                    )
                                )
                                
                                fig.update_layout(
                                    title=f"{selected_strategy} Performance",
                                    xaxis_title="Date",
                                    yaxis_title="Return ($)",
                                    height=400,
                                    template="plotly_dark",
                                    margin=dict(l=0, r=0, t=40, b=0)
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("No trade data available for performance chart.")
                        else:
                            st.info("No completed trades found for this strategy.")
                    else:
                        st.error("Strategy not found.")
            else:
                st.info("No performance metrics available yet. Start trading to generate performance data.")
            
            performance_session.close()
        
        # Logs tab
        with algo_tabs[4]:
            st.subheader("Trading Bot Logs")
            
            # Display most recent trades from database
            logs_session = Session(bind=engine)
            recent_trades = logs_session.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
            
            if recent_trades:
                for trade in recent_trades:
                    status_color = {
                        "PENDING": "blue",
                        "FILLED": "green",
                        "CANCELLED": "orange",
                        "REJECTED": "red"
                    }.get(trade.status, "gray")
                    
                    # Get strategy name
                    strategy = logs_session.query(Strategy).filter_by(id=trade.strategy_id).first()
                    strategy_name = strategy.name if strategy else "Unknown"
                    
                    st.markdown(
                        f"<div style='padding: 10px; border-left: 4px solid {status_color};'>"
                        f"<strong>{trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</strong> - "
                        f"<span style='color: {status_color};'>{trade.status}</span><br>"
                        f"Strategy: {strategy_name} | "
                        f"Order: {trade.direction} {trade.quantity} {trade.symbol} @ ${trade.price:.2f}<br>"
                        f"Order ID: {trade.order_id}<br>"
                        f"{'' if trade.exit_price is None else f'Exit: ${trade.exit_price:.2f} | P/L: ${trade.profit_loss:.2f} ({trade.profit_loss_percent:.2f}%)'}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
            else:
                st.info("No trading activity recorded yet.")
