import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# Page Config
st.set_page_config(
    page_title="Kalshi Bot Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constants
LOG_FILE = Path("logs/bot.log")

# --- Helper Functions ---
@st.cache_data(ttl=5)  # Refresh data every 5 seconds
def load_data():
    if not LOG_FILE.exists():
        return None
    
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        return None

def calculate_metrics(trades):
    if not trades:
        return None
    
    df = pd.DataFrame(trades)
    
    # Ensure numeric columns
    df['pnl'] = pd.to_numeric(df['pnl'])
    df['return_pct'] = pd.to_numeric(df.get('return_pct', 0))
    
    # Basic Metrics
    total_pnl = df['pnl'].sum()
    win_rate = (len(df[df['pnl'] > 0]) / len(df)) * 100
    total_trades = len(df)
    
    # Profit Factor
    gross_profit = df[df['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    return {
        'df': df,
        'total_pnl': total_pnl,
        'win_rate': win_rate,
        'total_trades': total_trades,
        'profit_factor': profit_factor
    }

# --- Main Dashboard ---
def main():
    st.title("🤖 Kalshi Trading Bot Dashboard")
    
    # Sidebar
    st.sidebar.header("Status")
    if LOG_FILE.exists():
        st.sidebar.success("Log File Found")
        last_update = datetime.fromtimestamp(LOG_FILE.stat().st_mtime)
        st.sidebar.text(f"Last Update: {last_update.strftime('%H:%M:%S')}")
    else:
        st.sidebar.error("Log File Not Found")
    
    if st.sidebar.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # Load Data
    data = load_data()
    
    if not data or 'trades' not in data or not data['trades']:
        st.info("Waiting for trades... (No data in history file yet)")
        return

    metrics = calculate_metrics(data['trades'])
    df = metrics['df']

    # --- Top Metrics Row ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total P&L", f"${metrics['total_pnl']:.2f}", 
                 delta_color="normal" if metrics['total_pnl'] >= 0 else "inverse")
    
    with col2:
        st.metric("Win Rate", f"{metrics['win_rate']:.1f}%")
        
    with col3:
        st.metric("Total Trades", metrics['total_trades'])
        
    with col4:
        st.metric("Profit Factor", f"{metrics['profit_factor']:.2f}")

    # --- Equity Curve ---
    st.subheader("📈 Equity Curve")
    
    # Calculate cumulative P&L
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['trade_num'] = range(1, len(df) + 1)
    
    fig = px.line(df, x='trade_num', y='cumulative_pnl', 
                  title='Account Growth', markers=True)
    fig.update_layout(xaxis_title="Trade #", yaxis_title="Cumulative P&L ($)")
    
    # Add zero line
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    st.plotly_chart(fig, use_container_width=True)

    # --- Recent Trades Table ---
    st.subheader("📋 Recent Trades")
    
    # Format table
    display_df = df[['market_id', 'side', 'entry_price', 'exit_price', 'pnl', 'exit_reason']].copy()
    display_df['pnl'] = display_df['pnl'].map('${:,.2f}'.format)
    display_df['entry_price'] = display_df['entry_price'].map('${:,.4f}'.format)
    
    st.dataframe(display_df.iloc[::-1].head(10), use_container_width=True)  # Show last 10 reversed

    # --- Strategy Performance (If available) ---
    if 'strategy' in df.columns:
        st.subheader("📊 Performance by Strategy")
        strategy_pnl = df.groupby('strategy')['pnl'].sum().reset_index()
        
        fig2 = px.bar(strategy_pnl, x='strategy', y='pnl', 
                     color='pnl', color_continuous_scale='RdGn')
        st.plotly_chart(fig2, use_container_width=True)

if __name__ == "__main__":
    main()
