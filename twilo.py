import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import time

# For Twilio integration (optional)
try:
    from twilio.rest import Client
except ImportError:
    print("Twilio not installed. Run 'pip install twilio' for WhatsApp notifications.")

# --- Secure Configuration ---
# Store these in environment variables or .env file, NOT in your code
def get_twilio_config():
    return {
        'sid': os.environ.get('AC06f43da521534aa566205b6b183f03be'),
        'token': os.environ.get('2759b9f2fff698e56dfe1b620307745f'),
        'from_number': os.environ.get('+14155238886'),
        'to_number': os.environ.get('+918967866349')
    }

# --- WhatsApp Notification Function ---
def send_whatsapp_message(body):
    try:
        config = get_twilio_config()
        
        # Check if configuration exists
        if not all(config.values()):
            print("Twilio configuration missing. Set environment variables for WhatsApp functionality.")
            return False
            
        client = Client(config['sid'], config['token'])
        message = client.messages.create(
            body=body,
            from_=config['from_number'],
            to=config['to_number']
        )
        print(f"WhatsApp message sent: {message.sid}")
        return True
    except Exception as e:
        print(f"Failed to send WhatsApp message: {str(e)}")
        return False

# --- NSE 500 Data Fetching ---
def get_nse_500_symbols():
    try:
        url = "https://www1.nseindia.com/content/indices/ind_nifty500list.csv"
        df = pd.read_csv(url)
        return [symbol + ".NS" for symbol in df['Symbol']]
    except Exception as e:
        print(f"Error fetching NSE 500 symbols: {e}")
        # Fallback to a smaller sample for testing if needed
        return ["RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS"]

# --- Breakout Detection Logic ---
def get_breakout_stocks(symbols, breakout_percent=1.0, lookback_periods=5):
    trades = []
    total_symbols = len(symbols)
    
    print(f"Scanning {total_symbols} symbols for breakouts...")
    
    for i, symbol in enumerate(symbols):
        if i % 50 == 0:
            print(f"Progress: {i}/{total_symbols} symbols processed")
            
        try:
            # Get data with enough lookback for analysis
            data = yf.download(symbol, period="2d", interval="15m", progress=False)
            
            if data.empty or len(data) < lookback_periods + 1:
                continue
                
            # Find recent high
            recent_high = data.iloc[-lookback_periods-1:-1]['High'].max()
            last_candle = data.iloc[-2]
            current_candle = data.iloc[-1]
            
            # Calculate breakout threshold
            breakout_price = recent_high * (1 + breakout_percent/100)
            
            # Check if current price broke above the threshold
            if current_candle['Close'] > breakout_price and current_candle['Volume'] > data.iloc[-lookback_periods-1:-1]['Volume'].mean():
                entry_price = current_candle['Close']
                
                # Calculate risk and target (you can adjust these parameters)
                atr = data.iloc[-lookback_periods-1:-1]['High'].max() - data.iloc[-lookback_periods-1:-1]['Low'].min()
                target = entry_price + (atr * 2)  # 2:1 reward-to-risk
                stop_loss = entry_price - (atr * 1)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                trades.append({
                    'symbol': symbol.replace(".NS", ""),
                    'entry_price': round(entry_price, 2),
                    'target': round(target, 2),
                    'stop_loss': round(stop_loss, 2),
                    'volume_change': round(current_candle['Volume'] / data.iloc[-lookback_periods-1:-1]['Volume'].mean(), 1),
                    'timestamp': timestamp
                })
                
        except Exception as e:
            # Just continue without verbose errors for every symbol
            continue
            
    return trades

# --- Main Scanner Function ---
def run_scanner(test_mode=False):
    print(f"Starting breakout scanner at {datetime.now().strftime('%Y-%m-%d %H:%M')}...")
    
    now = datetime.now()
    
    # Skip on weekends (0 is Monday, 6 is Sunday)
    if not test_mode and (now.weekday() >= 5 or now.hour < 9 or now.hour > 15):
        msg = f"Market is closed now. Scanner ran at {now.strftime('%H:%M')}."
        print(msg)
        
        # Only send message during weekday trading hours
        if 9 <= now.hour <= 15 and now.weekday() < 5:
            send_whatsapp_message(msg)
        return
    
    # Get symbols and detect breakouts
    symbols = get_nse_500_symbols()
    trades = get_breakout_stocks(symbols)
    
    if trades:
        print(f"Found {len(trades)} breakout trades!")
        message_body = f"🚀 NSE Breakout Scanner - {now.strftime('%d-%b-%Y %H:%M')}\n\n"
        
        # Sort by volume change for better quality signals
        trades.sort(key=lambda x: x['volume_change'], reverse=True)
        
        for trade in trades:
            line = f"🔸 {trade['symbol']}\n"
            line += f"Entry: ₹{trade['entry_price']} | Target: ₹{trade['target']} | SL: ₹{trade['stop_loss']}\n"
            line += f"Volume: {trade['volume_change']}x avg\n\n"
            message_body += line
            
        message_body += "📊 Use strict stop losses. Not financial advice."
        
        print(message_body)
        if not test_mode:
            send_whatsapp_message(message_body)
    else:
        msg = f"No breakout signals at {now.strftime('%H:%M')}."
        print(msg)
        if not test_mode:
            send_whatsapp_message(msg)

# --- Scheduled Execution ---
def run_scheduled_scanner(interval_minutes=60, test_run=False):
    """Run the scanner at specified intervals during market hours"""
    if test_run:
        print("Running in TEST mode")
        run_scanner(test_mode=True)
        return
        
    try:
        while True:
            now = datetime.now()
            # Only run during market hours on weekdays
            if now.weekday() < 5 and 9 <= now.hour <= 15:
                run_scanner()
            else:
                print(f"Market closed at {now.strftime('%H:%M')}. Waiting for next check.")
                
            # Sleep until next interval
            print(f"Sleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("Scanner stopped by user.")

# --- Example Usage ---
if __name__ == "__main__":
    # For a single run:
    run_scanner(test_mode=True)
    
    # For continuous monitoring (uncomment below):
    # run_scheduled_scanner(interval_minutes=30)