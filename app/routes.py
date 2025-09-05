from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import User, Configuration, Log
from app.utils import start_monitoring, stop_monitoring
from app.forms import ConfigurationForm
import json

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    configurations = current_user.configurations.all()
    return render_template('index.html', configurations=configurations)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    configurations = current_user.configurations.all()
    stats = {
        'total_configs': configurations.count(),
        'active_configs': configurations.filter_by(is_active=True).count(),
        'inactive_configs': configurations.filter_by(is_active=False).count(),
    }
    return render_template('dashboard.html', stats=stats, configurations=configurations)

@main_bp.route('/configuration/new', methods=['GET', 'POST'])
@login_required
def new_configuration():
    form = ConfigurationForm()
    if form.validate_on_submit():
        config = Configuration(
            name=form.name.data,
            spreadsheet_id=form.spreadsheet_id.data,
            worksheet_name=form.worksheet_name.data,
            sender_email=form.sender_email.data,
            gmail_app_password=form.gmail_app_password.data,
            recipient_email=form.recipient_email.data,
            poll_interval=form.poll_interval.data,
            user=current_user
        )
        db.session.add(config)
        db.session.commit()
        
        if config.is_active:
            start_monitoring(config, current_app.config['GOOGLE_CREDENTIALS_PATH'])
        
        flash('Configuration created successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('configuration_form.html', form=form, title='New Configuration')

@main_bp.route('/configuration/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_configuration(id):
    config = Configuration.query.get_or_404(id)
    if config.user != current_user:
        flash('You do not have permission to edit this configuration.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    form = ConfigurationForm(obj=config)
    if form.validate_on_submit():
        was_active = config.is_active
        
        form.populate_obj(config)
        db.session.commit()
        
        if was_active and not config.is_active:
            stop_monitoring(config.id)
        elif not was_active and config.is_active:
            start_monitoring(config, current_app.config['GOOGLE_CREDENTIALS_PATH'])
        elif was_active and config.is_active:
            stop_monitoring(config.id)
            start_monitoring(config, current_app.config['GOOGLE_CREDENTIALS_PATH'])
        
        flash('Configuration updated successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    
    return render_template('configuration_form.html', form=form, title='Edit Configuration')

@main_bp.route('/configuration/<int:id>/delete', methods=['POST'])
@login_required
def delete_configuration(id):
    config = Configuration.query.get_or_404(id)
    if config.user != current_user:
        flash('You do not have permission to delete this configuration.', 'danger')
        return redirect(url_for('main.dashboard'))
    
    if config.id in current_app.monitor_threads:
        stop_monitoring(config.id)
    
    db.session.delete(config)
    db.session.commit()
    
    flash('Configuration deleted successfully!', 'success')
    return redirect(url_for('main.dashboard'))

@main_bp.route('/configuration/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_configuration(id):
    config = Configuration.query.get_or_404(id)
    if config.user != current_user:
        return jsonify({'status': 'error', 'message': 'Permission denied'})
    
    config.is_active = not config.is_active
    db.session.commit()
    
    if config.is_active:
        start_monitoring(config, current_app.config['GOOGLE_CREDENTIALS_PATH'])
        return jsonify({'status': 'success', 'message': 'Monitoring started', 'is_active': True})
    else:
        stop_monitoring(config.id)
        return jsonify({'status': 'success', 'message': 'Monitoring stopped', 'is_active': False})

@main_bp.route('/api/logs/<int:config_id>')
@login_required
def get_logs(config_id):
    config = Configuration.query.get_or_404(config_id)
    if config.user != current_user:
        return jsonify({'status': 'error', 'message': 'Permission denied'})
    
    logs = config.logs.order_by(Log.created_at.desc()).limit(50).all()
    logs_data = [{
        'id': log.id,
        'message': log.message,
        'level': log.level,
        'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for log in logs]
    
    return jsonify({'status': 'success', 'logs': logs_data})

@main_bp.route('/api/stats')
@login_required
def get_stats():
    total_configs = current_user.configurations.count()
    active_configs = current_user.configurations.filter_by(is_active=True).count()
    
    return jsonify({
        'status': 'success',
        'stats': {
            'total_configs': total_configs,
            'active_configs': active_configs,
            'inactive_configs': total_configs - active_configs
        }
    })