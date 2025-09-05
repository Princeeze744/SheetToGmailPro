import gspread
from google.oauth2.service_account import Credentials
from threading import Thread
import time
from app import db
from app.models import Log

# Store active monitoring threads
monitors = {}

def authenticate_google():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 
                 'https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
        return gspread.authorize(creds)
    except Exception as e:
        return None

def monitor_sheet(config):
    client = authenticate_google()
    if not client:
        log_message(config.id, f'Failed to authenticate with Google Sheets API', 'ERROR')
        return
    
    try:
        spreadsheet = client.open_by_key(config.spreadsheet_id)
        worksheet = spreadsheet.worksheet(config.worksheet_name)
        last_row_count = len(worksheet.get_all_values())
        
        log_message(config.id, f'Started monitoring. Initial rows: {last_row_count}', 'INFO')
        
        while config.id in monitors and monitors[config.id]['running']:
            try:
                all_values = worksheet.get_all_values()
                current_row_count = len(all_values)
                
                if current_row_count > last_row_count:
                    new_rows = all_values[last_row_count:]
                    log_message(config.id, f'Found {len(new_rows)} new rows', 'SUCCESS')
                    
                    # Process new rows (send emails, etc.)
                    process_new_rows(config, new_rows)
                    
                    last_row_count = current_row_count
                
                time.sleep(config.poll_interval)
                
            except Exception as e:
                log_message(config.id, f'Monitoring error: {str(e)}', 'ERROR')
                time.sleep(60)  # Wait before retrying
                
    except Exception as e:
        log_message(config.id, f'Failed to start monitoring: {str(e)}', 'ERROR')

def process_new_rows(config, new_rows):
    # Implement your email sending logic here
    for row in new_rows:
        log_message(config.id, f'Processing row: {row}', 'INFO')
        # Send email logic would go here

def log_message(config_id, message, level='INFO'):
    log_entry = Log(config_id=config_id, message=message, level=level)
    db.session.add(log_entry)
    db.session.commit()

def start_monitoring(config):
    if config.id in monitors:
        return  # Already monitoring
    
    monitors[config.id] = {
        'running': True,
        'thread': Thread(target=monitor_sheet, args=(config,))
    }
    monitors[config.id]['thread'].daemon = True
    monitors[config.id]['thread'].start()

def stop_monitoring(config_id):
    if config_id in monitors:
        monitors[config_id]['running'] = False
        del monitors[config_id]