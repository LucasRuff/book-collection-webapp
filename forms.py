from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, BooleanField, TextAreaField, SelectMultipleField, SelectField, SubmitField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


READING_STATUS_CHOICES = [
    ('to_read', 'To Be Read'),
    ('in_progress', 'In Progress'),
    ('read', 'Read'),
    ('dnf', 'DNF'),
    ('to_work', 'To Be Worked'),
    ('reference', 'Reference'),
    ('coffee_table', 'Coffee Table Book'),
]

OWNERSHIP_STATUS_CHOICES = [
    ('owned', 'Owned'),
    ('not_owned', 'Not Owned'),
    ('subscription', 'Subscription'),
    ('wishlist', 'Wishlist'),
    ('borrowed', 'Borrowed'),
    ('lent_out', 'Lent Out'),
]

FORMAT_CHOICES = [
    ('physical', 'Physical'),
    ('ebook', 'E-book'),
    ('audiobook', 'Audiobook'),
]


class BookForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(max=300)])
    authors = SelectMultipleField('Authors', coerce=int, validators=[Optional()])
    new_authors = StringField('Add New Authors (comma-separated)', validators=[Optional(), Length(max=500)])
    publisher = SelectField('Publisher', coerce=int, validators=[Optional()])
    new_publisher = StringField('Or Add New Publisher', validators=[Optional(), Length(max=200)])
    publication_year = IntegerField('Publication Year', validators=[Optional(), NumberRange(min=0, max=2100)])
    isbn = StringField('ISBN', validators=[Optional(), Length(max=20)])
    reading_status = SelectField('Reading Status', choices=READING_STATUS_CHOICES, default='to_read')
    ownership_status = SelectField('Ownership Status', choices=OWNERSHIP_STATUS_CHOICES, default='owned')
    formats = SelectMultipleField('Formats', choices=FORMAT_CHOICES, default=['physical'])
    language = StringField('Language', validators=[Optional(), Length(max=50)], default='English')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Book')


class AuthorForm(FlaskForm):
    name = StringField('Author Name', validators=[DataRequired(), Length(max=200)])
    submit = SubmitField('Save Author')


class PublisherForm(FlaskForm):
    name = StringField('Publisher Name', validators=[DataRequired(), Length(max=200)])
    submit = SubmitField('Save Publisher')


class ComicSeriesForm(FlaskForm):
    name = StringField('Series Name', validators=[DataRequired(), Length(max=300)])
    volume = IntegerField('Volume Number', validators=[Optional(), NumberRange(min=1)])
    start_year = IntegerField('Start Year', validators=[Optional(), NumberRange(min=1900, max=2100)])
    publisher = SelectField('Publisher', coerce=int, validators=[Optional()])
    new_publisher = StringField('Or Add New Publisher', validators=[Optional(), Length(max=200)])
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Series')


class ComicIssueForm(FlaskForm):
    series = SelectField('Series', coerce=int, validators=[DataRequired()])
    issue_number = FloatField('Issue Number', validators=[DataRequired()])
    title = StringField('Issue Title (optional)', validators=[Optional(), Length(max=300)])
    cover_date = StringField('Cover Date', validators=[Optional(), Length(max=50)])
    cover_variant = StringField('Cover Variant', validators=[Optional(), Length(max=100)])
    authors = SelectMultipleField('Creative Team', coerce=int, validators=[Optional()])
    new_authors = StringField('Add New Creators (comma-separated)', validators=[Optional(), Length(max=500)])
    is_read = BooleanField('I have read this issue')
    notes = TextAreaField('Notes', validators=[Optional()])
    submit = SubmitField('Save Issue')


class QuickAddIssuesForm(FlaskForm):
    """Form for quickly adding multiple issues to a series."""
    series = SelectField('Series', coerce=int, validators=[DataRequired()])
    issue_numbers = StringField('Issue Numbers', validators=[DataRequired(), Length(max=500)])
    submit = SubmitField('Add Issues')


class SearchForm(FlaskForm):
    query = StringField('Search', validators=[Optional()])
    read_filter = SelectMultipleField('Reading Status', 
                                      choices=[('read', 'Read'), ('unread', 'Unread')],
                                      validators=[Optional()])
    submit = SubmitField('Search')
