from flask import current_app
from flask_security.forms import LoginForm as BaseLoginForm
from wtforms import BooleanField, StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from app.models import User

class LoginForm(BaseLoginForm):
    """User Login form. """
    username = StringField('User name')
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

    # flask_security requires that LoginForm has <user> property of user to log in
    user = None

    def validate(self):
        self.user = User.query.filter_by(username=self.username.data).first()
        if self.user is None or not self.user.check_password(self.password.data):
            current_app.logger.warning(f"Failed attempt to log in as <{self.username.data}>")
            return False
        current_app.logger.info(f"User {self.user} is logged in")
        return True