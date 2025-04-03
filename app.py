from flask import Flask, render_template, request, jsonify, redirect, url_for
import io
import datetime
import os
import json
import uuid
import csv
from dateutil import parser

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
                
                # Process the data
                report = generate_report(content)
                
                # Store report with a unique ID
                report_id = str(uuid.uuid4())
                REPORTS[report_id] = report
                
                return render_template('index.html', report=report, report_id=report_id)
            except Exception as e:
                return render_template('index.html', error=f"Error processing file: {str(e)}")
        else:
            return render_template('index.html', error="Please upload a CSV file")
    
    return render_template('index.html')

def parse_csv(csv_content):
    """Parse CSV content without pandas"""
    reader = csv.DictReader(io.StringIO(csv_content))
    rows = []
    for row in reader:
        rows.append(row)
    return rows

def filter_by_date(rows, date_field, target_date):
    """Filter rows by date"""
    filtered = []
    for row in rows:
        try:
            row_date = parser.parse(row[date_field]).strftime('%Y-%m-%d')
            if row_date == target_date:
                filtered.append(row)
        except (ValueError, KeyError):
            continue
    return filtered

def sum_field(rows, field):
    """Sum values in a field"""
    total = 0
    for row in rows:
        try:
            total += float(row[field])
        except (ValueError, KeyError):
            continue
    return total

def group_by(rows, group_fields, sum_field):
    """Group by fields and sum values"""
    groups = {}
    for row in rows:
        # Create group key from field values
        key_parts = []
        for field in group_fields:
            key_parts.append(row.get(field, ''))
        key = tuple(key_parts)
        
        # Sum values
        try:
            val = float(row.get(sum_field, 0))
            if key in groups:
                groups[key] += val
            else:
                groups[key] = val
        except ValueError:
            continue
    
    return groups

def generate_report(csv_content):
    """
    Generate the daily report from CSV content
    """
    # Parse CSV
    rows = parse_csv(csv_content)
    
    # Extract yesterday's date
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    day_before = (datetime.datetime.now() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    week_before = (datetime.datetime.now() - datetime.timedelta(days=8)).strftime('%Y-%m-%d')
    
    # Filter for dates
    yesterday_data = filter_by_date(rows, 'origin_timestamp', yesterday)
    day_before_data = filter_by_date(rows, 'origin_timestamp', day_before)
    week_before_data = filter_by_date(rows, 'origin_timestamp', week_before)
    
    # Calculate volumes
    yesterday_volume = sum_field(yesterday_data, 'from_asset_amount_usd')
    day_before_volume = sum_field(day_before_data, 'from_asset_amount_usd')
    week_before_volume = sum_field(week_before_data, 'from_asset_amount_usd')
    
    # Calculate day-over-day change
    dod_change = 0
    if day_before_volume > 0:
        dod_change = ((yesterday_volume - day_before_volume) / day_before_volume) * 100
    
    # Calculate week-over-week change
    wow_change = 0
    if week_before_volume > 0:
        wow_change = ((yesterday_volume - week_before_volume) / week_before_volume) * 100
    
    # Filter user vs MM transactions
    user_data = [r for r in yesterday_data if r.get('Market Maker Metadata - origin_initiator → Name') != 'Market Maker Bot']
    mm_data = [r for r in yesterday_data if r.get('Market Maker Metadata - origin_initiator → Name') == 'Market Maker Bot']
    
    # Get top pathways for users only
    pathway_groups = group_by(
        user_data, 
        ['from_chain_name', 'to_chain_name', 'from_asset_symbol'], 
        'from_asset_amount_usd'
    )
    
    # Sort pathways by volume
    sorted_pathways = sorted(pathway_groups.items(), key=lambda x: x[1], reverse=True)
    
    # Take top 3 pathways
    top_pathways = []
    for (from_chain, to_chain, asset), volume in sorted_pathways[:3]:
        top_pathways.append({
            'path': f"{from_chain} > {to_chain} - {asset}",
            'volume': volume
        })
    
    # Calculate transaction counts and average size
    user_tx_count = len(user_data)
    avg_tx_size = sum_field(user_data, 'from_asset_amount_usd') / user_tx_count if user_tx_count > 0 else 0
    
    # Get top users - dynamically calculate for all users
    user_volumes = group_by(user_data, ['Rebalancers Metadata - origin_initiator → Name'], 'from_asset_amount_usd')
    
    # Filter out any None/empty keys
    user_volumes = {k: v for k, v in user_volumes.items() if k[0]}
    
    # Get market maker data
    mm_bot_volume = sum_field(mm_data, 'from_asset_amount_usd')
    mm_bot_count = len(mm_data)
    
    # Create a dictionary to hold market maker volumes
    market_maker_volumes = {}
    
    # Calculate market maker volumes for all transactions
    # Use Market Maker Metadata for this section
    for row in yesterday_data:
        name = row.get('Market Maker Metadata - origin_initiator → Name')
        if not name or name == '':
            continue
        
        # Skip if already processed this MM
        if name in market_maker_volumes:
            continue
            
        # Get all rows for this market maker
        mm_rows = [r for r in yesterday_data if r.get('Market Maker Metadata - origin_initiator → Name') == name]
        
        # Calculate volume - excluding Blast to ETH for Tokka
        if name == 'tokka':
            # Filter out Blast to ETH transactions
            filtered_rows = [r for r in mm_rows if not (
                r.get('from_chain_name') == 'blast' and r.get('to_chain_name') == 'ethereum'
            )]
            volume = sum_field(filtered_rows, 'from_asset_amount_usd')
        else:
            volume = sum_field(mm_rows, 'from_asset_amount_usd')
        
        market_maker_volumes[name] = volume
    
    # Format numbers
    formatted_volume = f"${yesterday_volume/1000000:.2f}M"
    formatted_dod = f"{dod_change:.0f}%"
    formatted_wow = f"{wow_change:.0f}%"
    
    # Prepare top users for the report
    top_users_list = []
    # Sort users by volume and take top 3
    sorted_users = sorted(user_volumes.items(), key=lambda x: x[1], reverse=True)[:3]
    for (name,), volume in sorted_users:
        top_users_list.append({
            'name': name,
            'volume': f"${volume/1000000:.2f}M"
        })
    
    # Prepare top market makers for the report - get up to 3
    top_market_makers_list = []
    # Sort by volume and take up to 3 (if there are 3+ market makers)
    max_market_makers = min(3, len(market_maker_volumes))
    sorted_mms = sorted(market_maker_volumes.items(), key=lambda x: x[1], reverse=True)[:max_market_makers]
    for name, volume in sorted_mms:
        top_market_makers_list.append({
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
        'top_market_makers': top_market_makers_list,
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
    for rebalancer in report['top_market_makers']:
        text += f"- Top market maker #{report['top_market_makers'].index(rebalancer) + 1} — {rebalancer['volume']} volume closed ({rebalancer['name']})\n"
    
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