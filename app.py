from flask import Flask, render_template, request, flash, session
import pandas as pd
import io
import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return render_template('index.html')
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return render_template('index.html')
        
        if file and file.filename.endswith('.csv'):
            # Read the CSV file
            content = file.read().decode('utf-8')
            df = pd.read_csv(io.StringIO(content))
            
            # Process the data
            report = generate_report(df)
            
            # Store report in session
            session['report'] = report
            
            return render_template('index.html', report=report)
        else:
            flash('Please upload a CSV file')
    
    return render_template('index.html')

def generate_report(df):
    """
    Generate the daily report from the DataFrame
    """
    # Extract yesterday's date
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    day_before = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    week_before = (datetime.datetime.now() - datetime.timedelta(days=8)).strftime('%Y-%m-%d')
    
    # Convert timestamp columns to datetime
    df['origin_timestamp'] = pd.to_datetime(df['origin_timestamp'])
    
    # Filter for yesterday's data
    yesterday_data = df[df['origin_timestamp'].dt.strftime('%Y-%m-%d') == yesterday]
    day_before_data = df[df['origin_timestamp'].dt.strftime('%Y-%m-%d') == day_before]
    week_before_data = df[df['origin_timestamp'].dt.strftime('%Y-%m-%d') == week_before]
    
    # Calculate volumes
    yesterday_volume = yesterday_data['from_asset_amount_usd'].sum()
    day_before_volume = day_before_data['from_asset_amount_usd'].sum()
    week_before_volume = week_before_data['from_asset_amount_usd'].sum()
    
    # Calculate day-over-day change
    dod_change = 0
    if day_before_volume > 0:
        dod_change = ((yesterday_volume - day_before_volume) / day_before_volume) * 100
    
    # Calculate week-over-week change
    wow_change = 0
    if week_before_volume > 0:
        wow_change = ((yesterday_volume - week_before_volume) / week_before_volume) * 100
    
    # Filter user vs MM transactions
    user_data = yesterday_data[yesterday_data['Market Maker Metadata - origin_initiator → Name'] != 'Market Maker Bot']
    mm_data = yesterday_data[yesterday_data['Market Maker Metadata - origin_initiator → Name'] == 'Market Maker Bot']
    
    # Get top pathways for users only
    user_pathways = user_data.groupby(['from_chain_name', 'to_chain_name', 'from_asset_symbol'])['from_asset_amount_usd'].sum()
    top_pathways = []
    if not user_pathways.empty:
        for (from_chain, to_chain, asset), volume in user_pathways.nlargest(3).items():
            top_pathways.append({
                'path': f"{from_chain} > {to_chain} - {asset}",
                'volume': volume
            })
    
    # Calculate transaction counts and average size
    user_tx_count = len(user_data)
    avg_tx_size = user_data['from_asset_amount_usd'].mean() if user_tx_count > 0 else 0
    
    # Get top users
    tokka_volume = user_data[user_data['Rebalancers Metadata - origin_initiator → Name'] == 'tokka']['from_asset_amount_usd'].sum()
    
    tokka_rebalancer_volume = user_data[(user_data['Rebalancers Metadata - origin_initiator → Name'] == 'tokka') & 
                                      ~((user_data['from_chain_name'] == 'blast') & 
                                        (user_data['to_chain_name'] == 'ethereum'))]['from_asset_amount_usd'].sum()
    
    ali_volume = user_data[user_data['Rebalancers Metadata - origin_initiator → Name'] == 'ali']['from_asset_amount_usd'].sum()
    across_volume = user_data[user_data['Rebalancers Metadata - origin_initiator → Name'] == 'unknown across']['from_asset_amount_usd'].sum()
    
    # Get top rebalancers
    mm_bot_volume = mm_data['from_asset_amount_usd'].sum()
    mm_bot_count = len(mm_data)
    
    # Format numbers
    formatted_volume = f"${yesterday_volume/1000000:.2f}M"
    formatted_dod = f"{dod_change:.0f}%"
    formatted_wow = f"{wow_change:.0f}%"
    
    # Prepare the report
    report = {
        'date': yesterday.split('-')[2],
        'month': datetime.datetime.strptime(yesterday.split('-')[1], '%m').strftime('%b'),
        'total_volume': formatted_volume,
        'dod_change': formatted_dod,
        'wow_change': formatted_wow,
        'top_pathways': top_pathways,
        'user_tx_count': user_tx_count,
        'avg_tx_size': f"${avg_tx_size/1000:.1f}k",
        'top_users': [
            {'name': 'Tokka', 'volume': f"${tokka_volume/1000000:.2f}M"},
            {'name': 'Ali', 'volume': f"${ali_volume/1000000:.2f}M"},
            {'name': 'Across', 'volume': f"${across_volume/1000000:.2f}M"}
        ],
        'top_rebalancers': [
            {'name': 'Market Maker Bot', 'volume': f"${mm_bot_volume/1000000:.2f}M"},
            {'name': 'Tokka', 'volume': f"${tokka_rebalancer_volume/1000000:.2f}M"}
        ],
        'mm_bot_count': mm_bot_count,
        'mm_bot_volume': f"${mm_bot_volume/1000000:.2f}M"
    }
    
    return report

def format_report_text(report):
    """Format the report as text in the required format"""
    text = f"**Metrics {report['month']} {report['date']}**\n\n"
    
    text += "Volume (last day)\n\n"
    text += f"- Total — {report['total_volume']} ({report['dod_change']} d-o-d; {report['wow_change']} w-o-w)\n"
    
    text += "- Top pathways (users only, not MM)\n"
    for pathway in report['top_pathways']:
        volume_in_millions = f"${pathway['volume']/1000000:.2f}M"
        text += f"    - {pathway['path']} - {volume_in_millions}\n"
    
    text += "\nTransactions (last day)\n\n"
    text += f"- Total # — {report['user_tx_count']}\n"
    text += f"- Average size — {report['avg_tx_size']}\n\n"
    
    text += "Users (last day)\n\n"
    for user in report['top_users']:
        text += f"- Top user #{report['top_users'].index(user) + 1} — {user['name']} {user['volume']}\n"
    
    text += "\nMMs:\n\n"
    for rebalancer in report['top_rebalancers']:
        text += f"- Top rebalancer #{report['top_rebalancers'].index(rebalancer) + 1} — {rebalancer['volume']} volume closed ({rebalancer['name']})\n"
    
    text += f"\nMarket Maker Bot (last day)\n\n"
    text += f"- Total # invoices filled — {report['mm_bot_count']}\n"
    text += f"- $M volume filled — {report['mm_bot_volume']}\n"
    
    return text

@app.route('/download-report')
def download_report():
    if 'report' in session:
        report = session['report']
        report_text = format_report_text(report)
        return render_template('download.html', report_text=report_text)
    else:
        flash('No report available to download')
        return render_template('index.html')

# The app variable is used by Vercel

if __name__ == '__main__':
    # Only used for local development
    app.run(debug=True) 