from flask import Flask, render_template, request, jsonify, redirect, url_for
import pandas as pd
import io
import datetime
import os
import json
import uuid

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Store reports in memory (will be cleared on function restart)
REPORTS = {}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', error="No file part")
        
        file = request.files['file']
        if file.filename == '':
            return render_template('index.html', error="No selected file")
        
        if file and file.filename.endswith('.csv'):
            try:
                # Read the CSV file
                content = file.read().decode('utf-8')
                df = pd.read_csv(io.StringIO(content))
                
                # Process the data
                report = generate_report(df)
                
                # Store report with a unique ID
                report_id = str(uuid.uuid4())
                REPORTS[report_id] = report
                
                return render_template('index.html', report=report, report_id=report_id)
            except Exception as e:
                return render_template('index.html', error=f"Error processing file: {str(e)}")
        else:
            return render_template('index.html', error="Please upload a CSV file")
    
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
    
    # Get top users - dynamically calculate for all users
    user_volumes = user_data.groupby('Rebalancers Metadata - origin_initiator → Name')['from_asset_amount_usd'].sum()
    
    # Get top users (excluding any missing/NaN values)
    user_volumes = user_volumes[user_volumes.index.notnull()]
    
    # Get top rebalancers
    mm_bot_volume = mm_data['from_asset_amount_usd'].sum()
    mm_bot_count = len(mm_data)
    
    # Create a dictionary to hold rebalancer volumes
    rebalancer_volumes = {}
    
    # Add Market Maker Bot
    if mm_bot_volume > 0:
        rebalancer_volumes['Market Maker Bot'] = mm_bot_volume
    
    # Calculate rebalancer volumes for all users (excluding Blast to ETH for Tokka)
    for name, group in user_data.groupby('Rebalancers Metadata - origin_initiator → Name'):
        if pd.isna(name):
            continue
        
        # For tokka, exclude Blast to ETH transactions
        if name == 'tokka':
            volume = group[~((group['from_chain_name'] == 'blast') & 
                           (group['to_chain_name'] == 'ethereum'))]['from_asset_amount_usd'].sum()
        else:
            volume = group['from_asset_amount_usd'].sum()
        
        rebalancer_volumes[name] = volume
    
    # Format numbers
    formatted_volume = f"${yesterday_volume/1000000:.2f}M"
    formatted_dod = f"{dod_change:.0f}%"
    formatted_wow = f"{wow_change:.0f}%"
    
    # Prepare top users for the report
    top_users_list = []
    for name, volume in user_volumes.nlargest(3).items():
        # If name is missing, use 'Unknown'
        user_name = name if pd.notna(name) else 'Unknown'
        top_users_list.append({
            'name': user_name,
            'volume': f"${volume/1000000:.2f}M"
        })
    
    # Prepare top rebalancers for the report - get top 2
    top_rebalancers_list = []
    for name, volume in sorted(rebalancer_volumes.items(), key=lambda x: x[1], reverse=True)[:2]:
        top_rebalancers_list.append({
            'name': name,
            'volume': f"${volume/1000000:.2f}M"
        })
    
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
        'top_users': top_users_list,
        'top_rebalancers': top_rebalancers_list,
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

@app.route('/download-report/<report_id>')
def download_report(report_id):
    if report_id in REPORTS:
        report = REPORTS[report_id]
        report_text = format_report_text(report)
        return render_template('download.html', report_text=report_text)
    else:
        return render_template('index.html', error="Report not found. Please generate a new report.")

# Handle 404 errors
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html', error="Page not found"), 404

# Handle 500 errors
@app.errorhandler(500)
def server_error(e):
    return render_template('index.html', error="Server error. Please try again."), 500

# The app variable is used by Vercel
app = app

if __name__ == '__main__':
    # Only used for local development
    app.run(debug=True) 