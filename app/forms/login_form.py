from flask import current_app, flash
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
        result = False
        if self.user is None:
            current_app.logger.warning(f"No user  <{self.username.data}> was found!")
        elif not self.user.enabled:
            current_app.logger.warning(f"User {self.user} is disabled!")
        elif not self.user.check_password(self.password.data):
            current_app.logger.warning(f"Failed attempt to log in as {self.user} because of wrong password!")
        else:
            current_app.logger.info(f"User {self.user} is logged in")
            result = True
        if not result:
            flash("Logon attempt has failed", category='error')
        return result
