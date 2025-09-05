from flask import Flask, render_template, request, jsonify
import threading
import time
import json
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production

# Configuration
CONFIG_FILE = 'config.json'
DB_FILE = 'app.db'

# Global variables
monitoring = False
monitor_thread = None
stats = {
    'emails_sent': 0,
    'rows_processed': 0,
    'last_check': None
}

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  level TEXT,
                  message TEXT)''')
    conn.commit()
    conn.close()

init_db()

def log_activity(level, message):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO activity_logs (level, message) VALUES (?, ?)", 
              (level, message))
    conn.commit()
    conn.close()

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
        client = gspread.authorize(creds)
        log_activity('INFO', 'Google authentication successful')
        return client
    except Exception as e:
        log_activity('ERROR', f'Google authentication failed: {str(e)}')
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

        stats['emails_sent'] += 1
        log_activity('SUCCESS', f"Email sent to {config['recipient_email']}")
        return True

    except Exception as e:
        log_activity('ERROR', f"Failed to send email: {str(e)}")
        return False

def monitor_sheet():
    global monitoring, stats
    config = load_config()
    client = authenticate_google()
    
    if not client:
        monitoring = False
        log_activity('ERROR', 'Failed to authenticate Google Sheets - monitoring stopped')
        return

    try:
        spreadsheet = client.open_by_key(config['spreadsheet_id'])
        worksheet = spreadsheet.worksheet(config['worksheet_name'])
        last_row_count = len(worksheet.get_all_values())

        log_activity('INFO', f"Started monitoring. Initial rows: {last_row_count}")

        while monitoring:
            try:
                all_values = worksheet.get_all_values()
                current_row_count = len(all_values)
                stats['last_check'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if current_row_count > last_row_count:
                    new_rows = all_values[last_row_count:]
                    log_activity('INFO', f"Found {len(new_rows)} new rows")
                    stats['rows_processed'] += len(new_rows)

                    for row in new_rows:
                        send_email(config, row)

                    last_row_count = current_row_count

                time.sleep(config['poll_interval'])

            except Exception as e:
                log_activity('ERROR', f"Monitoring error: {str(e)}")
                time.sleep(60)  # wait before retrying

    except Exception as e:
        log_activity('ERROR', f"Failed to start monitoring: {str(e)}")
    finally:
        monitoring = False
        log_activity('INFO', 'Monitoring stopped')

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
    log_activity('INFO', 'Configuration updated')
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
        log_activity('INFO', 'Monitoring started')
        return jsonify({'status': 'started'})
    else:
        # Stop monitoring
        monitoring = False
        log_activity('INFO', 'Monitoring stopped')
        return jsonify({'status': 'stopped'})

@app.route('/test_connection')
def test_connection():
    client = authenticate_google()
    if client:
        return jsonify({'status': 'success', 'message': 'Google connection successful'})
    else:
        return jsonify({'status': 'error', 'message': 'Google connection failed'})

@app.route('/test_email')
def test_email():
    config = load_config()
    test_row = ['Test Name', 'test@example.com', 'This is a test message', datetime.now().strftime('%Y-%m-%d')]
    success = send_email(config, test_row)
    
    if success:
        return jsonify({'status': 'success', 'message': 'Test email sent successfully'})
    else:
        return jsonify({'status': 'error', 'message': 'Failed to send test email'})

@app.route('/monitoring_status')
def monitoring_status():
    return jsonify({'monitoring': monitoring})

@app.route('/get_stats')
def get_stats():
    return jsonify(stats)

@app.route('/get_logs')
def get_logs():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT timestamp, level, message FROM activity_logs ORDER BY id DESC LIMIT 50")
    logs = c.fetchall()
    conn.close()
    
    return jsonify({'logs': logs})

if __name__ == '__main__':
    log_activity('INFO', 'Application started')
    app.run(debug=True, host='0.0.0.0', port=5000)