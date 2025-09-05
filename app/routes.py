from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from app import db
from app.models import User, Configuration, Log
from app.forms import LoginForm, RegistrationForm, ConfigurationForm
from app.utils import start_monitoring, stop_monitoring
import json

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/dashboard')
@login_required
def dashboard():
    configurations = current_user.configurations.all()
    return render_template('dashboard.html', title='Dashboard', configurations=configurations)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return redirect(url_for('main.login'))
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('main.dashboard'))
    return render_template('login.html', title='Sign In', form=form)

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html', title='Register', form=form)

@bp.route('/configuration/new', methods=['GET', 'POST'])
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
            owner=current_user
        )
        db.session.add(config)
        db.session.commit()
        
        # Start monitoring this configuration
        start_monitoring(config)
        
        flash('Configuration created successfully!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('configuration.html', title='New Configuration', form=form)

@bp.route('/configuration/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_configuration(id):
    config = Configuration.query.get_or_404(id)
    if config.owner != current_user:
        abort(403)
    
    config.is_active = not config.is_active
    db.session.commit()
    
    if config.is_active:
        start_monitoring(config)
        flash('Configuration activated!', 'success')
    else:
        stop_monitoring(config.id)
        flash('Configuration deactivated!', 'info')
    
    return redirect(url_for('main.dashboard'))

@bp.route('/api/status')
@login_required
def api_status():
    return jsonify({'status': 'success', 'message': 'API is working'})