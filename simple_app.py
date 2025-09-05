from flask import Flask, render_template, request, jsonify
import threading
import time
import json
import os
from datetime import datetime

# Import your existing automation code
import gspread
from google.oauth2.service_account import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

app = Flask(__name__)

# Configuration
CONFIG_FILE = 'config.json'

# Global variables
monitoring = False
monitor_thread = None

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        "spreadsheet_id": "",
        "worksheet_name": "Sheet1",
        "sender_email": "",
        "gmail_app_password": "",
        "recipient_email": "",
        "poll_interval": 30,
        "column_headers": ["Name", "Email", "Message", "Date"]
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def authenticate_google():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        return None

def send_email(config, row_data):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = config['sender_email']
        msg['To'] = config['recipient_email']
        msg['Subject'] = 'New Row Added to Google Sheet'

        body = f"A new row has been added to your Google Sheet:\n\n"
        for i, value in enumerate(row_data):
            header = config['column_headers'][i] if i < len(config['column_headers']) else f"Column {i+1}"
            body += f"{header}: {value}\n"
        body += f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(config['sender_email'], config['gmail_app_password'])
            server.send_message(msg)

        print(f"Email sent to {config['recipient_email']}")
        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

def monitor_sheet():
    global monitoring
    config = load_config()
    client = authenticate_google()
    if not client:
        print("Failed to authenticate Google Sheets")
        monitoring = False
        return

    try:
        spreadsheet = client.open_by_key(config['spreadsheet_id'])
        worksheet = spreadsheet.worksheet(config['worksheet_name'])
        last_row_count = len(worksheet.get_all_values())

        print(f"Started monitoring. Initial rows: {last_row_count}")

        while monitoring:
            try:
                all_values = worksheet.get_all_values()
                current_row_count = len(all_values)

                if current_row_count > last_row_count:
                    new_rows = all_values[last_row_count:]
                    print(f"Found {len(new_rows)} new rows")

                    for row in new_rows:
                        send_email(config, row)

                    last_row_count = current_row_count

                time.sleep(config['poll_interval'])

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(60)  # wait before retrying

    except Exception as e:
        print(f"Failed to start monitoring: {e}")
    finally:
        monitoring = False

@app.route('/')
def index():
    config = load_config()
    return render_template('index.html', config=config, monitoring=monitoring)

@app.route('/update_config', methods=['POST'])
def update_config():
    config = {
        "spreadsheet_id": request.form['spreadsheet_id'],
        "worksheet_name": request.form['worksheet_name'],
        "sender_email": request.form['sender_email'],
        "gmail_app_password": request.form['gmail_app_password'],
        "recipient_email": request.form['recipient_email'],
        "poll_interval": int(request.form['poll_interval']),
        "column_headers": ["Name", "Email", "Message", "Date"]
    }
    save_config(config)
    return jsonify({'status': 'success'})

@app.route('/toggle_monitoring', methods=['POST'])
def toggle_monitoring():
    global monitoring, monitor_thread

    if not monitoring:
        # Start monitoring
        monitoring = True
        monitor_thread = threading.Thread(target=monitor_sheet)
        monitor_thread.daemon = True
        monitor_thread.start()
        return jsonify({'status': 'started'})
    else:
        # Stop monitoring
        monitoring = False
        return jsonify({'status': 'stopped'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)