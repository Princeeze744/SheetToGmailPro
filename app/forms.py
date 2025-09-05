from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length
from app.models import User

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Please use a different email address.')

class ConfigurationForm(FlaskForm):
    name = StringField('Configuration Name', validators=[DataRequired()])
    spreadsheet_id = StringField('Spreadsheet ID', validators=[DataRequired()])
    worksheet_name = StringField('Worksheet Name', default='Sheet1')
    sender_email = StringField('Sender Email', validators=[DataRequired(), Email()])
    gmail_app_password = PasswordField('Gmail App Password', validators=[DataRequired()])
    recipient_email = StringField('Recipient Email', validators=[DataRequired(), Email()])
    poll_interval = IntegerField('Poll Interval (seconds)', default=30)
    submit = SubmitField('Save Configuration')