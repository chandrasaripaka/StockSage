import plotly.graph_objects as go
from utils import standardize_dataframe_columns

def create_candlestick_chart(data, include_volume=True, signals=None, title=None, height=600):
    """
    Create a standardized candlestick chart with consistent column access
    
    Parameters:
    data (pandas.DataFrame): DataFrame with price data
    include_volume (bool): Whether to include volume subplot
    signals (dict): Optional dictionary with 'buy' and 'sell' signals DataFrames
    title (str): Chart title (optional)
    height (int): Chart height
    
    Returns:
    plotly.graph_objects.Figure: Candlestick chart
    """
    # Standardize column names to ensure consistent access
    data = standardize_dataframe_columns(data)
    
    fig = go.Figure()
    
    # Add candlestick chart
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name="Price"
        )
    )
    
    # Add signals if provided
    if signals and 'buy' in signals and len(signals['buy']) > 0:
        buy_signals = signals['buy']
        fig.add_trace(
            go.Scatter(
                x=buy_signals.index,
                y=buy_signals['low'] * 0.99,  # Place slightly below the candle
                mode='markers',
                marker=dict(
                    color='green',
                    size=10,
                    symbol='triangle-up',
                    line=dict(width=2, color='white')
                ),
                name="Buy Signal"
            )
        )
    
    if signals and 'sell' in signals and len(signals['sell']) > 0:
        sell_signals = signals['sell']
        fig.add_trace(
            go.Scatter(
                x=sell_signals.index,
                y=sell_signals['high'] * 1.01,  # Place slightly above the candle
                mode='markers',
                marker=dict(
                    color='red',
                    size=10,
                    symbol='triangle-down',
                    line=dict(width=2, color='white')
                ),
                name="Sell Signal"
            )
        )
    
    # Add volume subplot if requested
    if include_volume and 'volume' in data.columns:
        # Create volume colors
        volume_colors = []
        for i in range(len(data)):
            if i > 0:
                if data['close'].iloc[i] > data['close'].iloc[i-1]:
                    volume_colors.append('rgba(0, 255, 0, 0.3)')
                else:
                    volume_colors.append('rgba(255, 0, 0, 0.3)')
            else:
                volume_colors.append('rgba(0, 255, 0, 0.3)')
        
        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data['volume'],
                marker_color=volume_colors,
                name="Volume",
                yaxis="y2"
            )
        )
        
        # Update layout for dual y-axis
        fig.update_layout(
            yaxis2=dict(
                title="Volume",
                overlaying="y",
                side="right",
                showgrid=False
            )
        )
    
    # Set chart title if provided
    if title:
        fig.update_layout(title=title)
        
    # Update layout
    fig.update_layout(
        height=height,
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, b=50, t=50),
        template="plotly_dark"
    )
    
    return fig

def create_price_chart(data, moving_averages=None, title=None, height=500):
    """
    Create a line chart of price data with optional moving averages
    
    Parameters:
    data (pandas.DataFrame): DataFrame with price data
    moving_averages (list): List of periods for moving averages to display
    title (str): Chart title (optional)
    height (int): Chart height
    
    Returns:
    plotly.graph_objects.Figure: Price chart
    """
    # Standardize column names
    data = standardize_dataframe_columns(data)
    
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data['close'],
            mode='lines',
            name='Price',
            line=dict(width=2, color='#00FFFF')
        )
    )
    
    # Add moving averages if requested
    if moving_averages:
        colors = ['#FF9900', '#FF00FF', '#FFFF00']
        for i, period in enumerate(moving_averages):
            ma_col = f'ma_{period}'
            if ma_col in data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=data.index,
                        y=data[ma_col],
                        mode='lines',
                        name=f'{period} MA',
                        line=dict(width=1.5, color=colors[i % len(colors)])
                    )
                )
    
    # Set chart title if provided
    if title:
        fig.update_layout(title=title)
        
    # Update layout
    fig.update_layout(
        height=height,
        xaxis_rangeslider_visible=False,
        margin=dict(l=50, r=50, b=50, t=50),
        template="plotly_dark",
        legend=dict(orientation="h", y=1.02)
    )
    
    return fig