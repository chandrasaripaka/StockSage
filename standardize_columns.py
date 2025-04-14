import streamlit as st
import plotly.graph_objects as go
from utils import standardize_dataframe_columns

def create_candlestick_chart(data, include_volume=True, title=None, height=600):
    """
    Create a standardized candlestick chart with consistent column access
    
    Parameters:
    data (pandas.DataFrame): DataFrame with price data
    include_volume (bool): Whether to include volume subplot
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
    
    # Add volume subplot if requested
    if include_volume and 'volume' in data.columns:
        # Create volume trace
        volume_colors = ['rgba(0, 255, 0, 0.3)' if data.loc[i, 'close'] > data.loc[i, 'open'] 
                        else 'rgba(255, 0, 0, 0.3)' 
                        for i in data.index]
        
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
        margin=dict(l=50, r=50, b=50, t=50)
    )
    
    return fig