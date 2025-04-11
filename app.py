import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import numpy as np
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
