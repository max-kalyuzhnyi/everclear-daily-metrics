# Daily Rewards Report Generator

A simple web application that generates standardized daily reports from CSV data files. Upload your transaction data, and the app will automatically analyze it and produce a formatted report.

## Features

- Easy file upload interface
- Automatic calculation of key metrics:
  - Total volume
  - Day-over-day and week-over-week volume changes
  - Top pathways by volume
  - Transaction counts and average size
  - Top users and their volumes
  - Market maker statistics
- Copy reports to clipboard with one click
- Download reports as text files

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd rewards-report-app
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the application locally:
   ```
   python app.py
   ```

2. Open your browser and navigate to `http://127.0.0.1:5000/`

3. Upload your CSV file through the interface

4. The report will be generated automatically and displayed on the page

5. You can copy the report to your clipboard or download it as a text file

## Deployment to Vercel

This application is pre-configured for deployment to Vercel:

1. Install the Vercel CLI:
   ```
   npm install -g vercel
   ```

2. Login to Vercel:
   ```
   vercel login
   ```

3. Deploy the application:
   ```
   vercel
   ```

4. Set a SECRET_KEY environment variable in the Vercel dashboard for session management:
   - Go to your project settings in the Vercel dashboard
   - Navigate to Environment Variables
   - Add a new variable with key `SECRET_KEY` and a secure random value

5. For production deployment:
   ```
   vercel --prod
   ```

Alternatively, you can connect your GitHub repository to Vercel for automatic deployments.

## CSV File Format

The application expects a CSV file with the following columns:

- `origin_timestamp`: The timestamp of when the transaction was initiated
- `from_chain_name`: The source blockchain
- `to_chain_name`: The destination blockchain
- `from_asset_symbol`: The token symbol being transferred
- `from_asset_amount_usd`: The USD value of the transaction
- `Market Maker Metadata - origin_initiator → Name`: Identifies if the transaction is from a market maker
- `Rebalancers Metadata - origin_initiator → Name`: Identifies the user name

## Customization

You can modify the report format by editing the `format_report_text` function in `app.py` or the template in `templates/index.html`. 