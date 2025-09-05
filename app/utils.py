import gspread
from google.oauth2.service_account import Credentials
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime
from app import db
from app.models import Log
import threading
import time

# Store active monitoring threads
monitor_threads = {}

def authenticate_google(credentials_path):
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 
                 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        return None

def send_email(config, row_data):
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = config.sender_email
        msg['To'] = config.recipient_email
        msg['Subject'] = 'New Row Added to Google Sheet'

        body = f"A new row has been added to your Google Sheet:\n\n"
        body += f"Configuration: {config.name}\n"
        body += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        body += "Row Data:\n"
        
        for i, value in enumerate(row_data):
            header = f"Column {i+1}"
            body += f"{header}: {value}\n"

        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(config.sender_email, config.gmail_app_password)
            server.send_message(msg)
            
        log_message(config.id, f"Email sent to {config.recipient_email}", "SUCCESS")
        return True
        
    except Exception as e:
        log_message(config.id, f"Failed to send email: {str(e)}", "ERROR")
        return False

def log_message(config_id, message, level="INFO"):
    log = Log(configuration_id=config_id, message=message, level=level)
    db.session.add(log)
    db.session.commit()

def monitor_configuration(config, credentials_path):
    client = authenticate_google(credentials_path)
    if not client:
        log_message(config.id, "Failed to authenticate with Google Sheets API", "ERROR")
        return
    
    try:
        spreadsheet = client.open_by_key(config.spreadsheet_id)
        worksheet = spreadsheet.worksheet(config.worksheet_name)
        last_row_count = len(worksheet.get_all_values())
        
        log_message(config.id, f"Started monitoring. Initial rows: {last_row_count}", "INFO")
        
        while config.id in monitor_threads and monitor_threads[config.id]['running']:
            try:
                all_values = worksheet.get_all_values()
                current_row_count = len(all_values)
                
                if current_row_count > last_row_count:
                    new_rows = all_values[last_row_count:]
                    log_message(config.id, f"Found {len(new_rows)} new rows", "INFO")
                    
                    for row in new_rows:
                        send_email(config, row)
                    
                    last_row_count = current_row_count
                
                time.sleep(config.poll_interval)
                
            except Exception as e:
                log_message(config.id, f"Monitoring error: {str(e)}", "ERROR")
                time.sleep(60)  # Wait before retrying
                
    except Exception as e:
        log_message(config.id, f"Failed to start monitoring: {str(e)}", "ERROR")
    finally:
        if config.id in monitor_threads:
            del monitor_threads[config.id]

def start_monitoring(config, credentials_path):
    if config.id in monitor_threads:
        return  # Already monitoring
    
    monitor_threads[config.id] = {
        'running': True,
        'thread': threading.Thread(target=monitor_configuration, args=(config, credentials_path))
    }
    monitor_threads[config.id]['thread'].daemon = True
    monitor_threads[config.id]['thread'].start()
    log_message(config.id, "Monitoring started", "INFO")

def stop_monitoring(config_id):
    if config_id in monitor_threads:
        monitor_threads[config_id]['running'] = False
        if config_id in monitor_threads:
            del monitor_threads[config_id]
        log_message(config_id, "Monitoring stopped", "INFO")