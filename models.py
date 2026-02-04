from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Association table for many-to-many relationship between books and authors
book_authors = db.Table('book_authors',
    db.Column('book_id', db.Integer, db.ForeignKey('book.id'), primary_key=True),
    db.Column('author_id', db.Integer, db.ForeignKey('author.id'), primary_key=True)
)

# Association table for many-to-many relationship between comic series and authors
series_authors = db.Table('series_authors',
    db.Column('series_id', db.Integer, db.ForeignKey('comic_series.id'), primary_key=True),
    db.Column('author_id', db.Integer, db.ForeignKey('author.id'), primary_key=True)
)


class ReadingQueue(db.Model):
    """Ordered queue of books to read next, per format. Position 1 = read next."""
    id = db.Column(db.Integer, primary_key=True)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    queue_format = db.Column(db.String(20), nullable=False, default='physical')  # physical, ebook, audiobook
    position = db.Column(db.Integer, nullable=False)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one entry per book per format
    __table_args__ = (db.UniqueConstraint('book_id', 'queue_format', name='unique_book_format'),)
    
    book = db.relationship('Book', backref=db.backref('queue_entries', lazy=True))
    
    def __repr__(self):
        return f'<ReadingQueue pos={self.position} format={self.queue_format} book_id={self.book_id}>'


class Author(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    
    def __repr__(self):
        return f'<Author {self.name}>'


class Publisher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    
    def __repr__(self):
        return f'<Publisher {self.name}>'


# Reading status choices
READING_STATUS_CHOICES = [
    ('to_read', 'To Be Read'),
    ('in_progress', 'In Progress'),
    ('read', 'Read'),
    ('dnf', 'DNF'),
    ('to_work', 'To Be Worked'),
    ('reference', 'Reference'),
    ('coffee_table', 'Coffee Table Book'),
]

READING_STATUS_LABELS = dict(READING_STATUS_CHOICES)

# Ownership status choices
OWNERSHIP_STATUS_CHOICES = [
    ('owned', 'Owned'),
    ('not_owned', 'Not Owned'),
    ('subscription', 'Subscription'),
    ('wishlist', 'Wishlist'),
    ('borrowed', 'Borrowed'),
    ('lent_out', 'Lent Out'),
]

OWNERSHIP_STATUS_LABELS = dict(OWNERSHIP_STATUS_CHOICES)

# Format choices
FORMAT_CHOICES = [
    ('physical', 'Physical'),
    ('ebook', 'E-book'),
    ('audiobook', 'Audiobook'),
]

FORMAT_LABELS = dict(FORMAT_CHOICES)


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    
    # Publication information - nullable for old/unknown books
    publisher_id = db.Column(db.Integer, db.ForeignKey('publisher.id'), nullable=True)
    publisher = db.relationship('Publisher', backref=db.backref('books', lazy=True))
    publication_year = db.Column(db.Integer, nullable=True)
    isbn = db.Column(db.String(20), nullable=True)
    
    # Reading status
    reading_status = db.Column(db.String(20), default='to_read', nullable=False)
    
    # Ownership status
    ownership_status = db.Column(db.String(20), default='owned', nullable=False)
    
    # Formats (comma-separated: physical, ebook, audiobook)
    formats = db.Column(db.String(100), default='physical', nullable=False)
    
    # Language
    language = db.Column(db.String(50), default='English', nullable=False)
    
    # Optional notes
    notes = db.Column(db.Text, nullable=True)
    
    # Timestamp
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Many-to-many relationship with authors
    authors = db.relationship('Author', secondary=book_authors, lazy='subquery',
                              backref=db.backref('books', lazy=True))
    
    def __repr__(self):
        return f'<Book {self.title}>'
    
    @property
    def reading_status_display(self):
        """Return the human-readable reading status."""
        return READING_STATUS_LABELS.get(self.reading_status, 'Unknown')
    
    @property
    def is_read(self):
        """Backward compatibility: returns True if status is 'read'."""
        return self.reading_status == 'read'
    
    @property
    def ownership_status_display(self):
        """Return the human-readable ownership status."""
        return OWNERSHIP_STATUS_LABELS.get(self.ownership_status, 'Unknown')
    
    @property
    def formats_list(self):
        """Return formats as a list."""
        if not self.formats:
            return []
        return [f.strip() for f in self.formats.split(',') if f.strip()]
    
    @formats_list.setter
    def formats_list(self, value):
        """Set formats from a list."""
        self.formats = ','.join(value) if value else 'physical'
    
    @property
    def formats_display(self):
        """Return human-readable format names."""
        return [FORMAT_LABELS.get(f, f) for f in self.formats_list]
    
    @property
    def authors_display(self):
        """Return a formatted string of all authors."""
        if not self.authors:
            return "Unknown Author"
        return ", ".join(author.name for author in self.authors)
    
    @property
    def publisher_display(self):
        """Return the publisher name or Unknown."""
        if not self.publisher:
            return "Unknown Publisher"
        return self.publisher.name


# Association table for many-to-many relationship between comic issues and authors
issue_authors = db.Table('issue_authors',
    db.Column('issue_id', db.Integer, db.ForeignKey('comic_issue.id'), primary_key=True),
    db.Column('author_id', db.Integer, db.ForeignKey('author.id'), primary_key=True)
)


class ComicSeries(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(300), nullable=False)
    volume = db.Column(db.Integer, nullable=True)  # For series that restart (e.g., Vol. 2)
    start_year = db.Column(db.Integer, nullable=True)
    
    publisher_id = db.Column(db.Integer, db.ForeignKey('publisher.id'), nullable=True)
    publisher = db.relationship('Publisher', backref=db.backref('comic_series', lazy=True))
    
    notes = db.Column(db.Text, nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to issues
    issues = db.relationship('ComicIssue', backref='series', lazy=True, order_by='ComicIssue.issue_number')
    
    # Default creative team for the series
    authors = db.relationship('Author', secondary='series_authors', lazy='subquery',
                              backref=db.backref('comic_series', lazy=True))
    
    def __repr__(self):
        if self.volume:
            return f'<ComicSeries {self.name} Vol. {self.volume}>'
        return f'<ComicSeries {self.name}>'
    
    @property
    def display_name(self):
        """Return formatted series name with volume if applicable."""
        if self.volume:
            return f"{self.name} (Vol. {self.volume})"
        if self.start_year:
            return f"{self.name} ({self.start_year})"
        return self.name
    
    @property
    def authors_display(self):
        """Return a formatted string of all authors/creators."""
        if not self.authors:
            return ""
        return ", ".join(author.name for author in self.authors)
    
    @property
    def issue_count(self):
        return len(self.issues)
    
    @property
    def read_count(self):
        return sum(1 for issue in self.issues if issue.is_read)
    
    @property
    def issue_numbers_display(self):
        """Return a summary of owned issue numbers."""
        if not self.issues:
            return "No issues"
        numbers = sorted([i.issue_number for i in self.issues])
        if len(numbers) <= 5:
            return ", ".join(f"#{n}" for n in numbers)
        return f"#{numbers[0]}-#{numbers[-1]} ({len(numbers)} issues)"


class ComicIssue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    series_id = db.Column(db.Integer, db.ForeignKey('comic_series.id'), nullable=False)
    issue_number = db.Column(db.Float, nullable=False)  # Float for .1, .5 issues
    
    title = db.Column(db.String(300), nullable=True)  # Some issues have titles
    cover_date = db.Column(db.String(50), nullable=True)  # e.g., "January 2020"
    
    # Variant cover info
    cover_variant = db.Column(db.String(100), nullable=True)  # e.g., "1:25 variant", "SDCC exclusive"
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Many-to-many relationship with authors (creative team)
    authors = db.relationship('Author', secondary=issue_authors, lazy='subquery',
                              backref=db.backref('comic_issues', lazy=True))
    
    def __repr__(self):
        return f'<ComicIssue {self.series.name} #{self.issue_number}>'
    
    @property
    def display_name(self):
        """Return formatted issue name."""
        base = f"{self.series.name} #{self.issue_number:g}"
        if self.cover_variant:
            base += f" ({self.cover_variant})"
        return base
    
    @property
    def authors_display(self):
        """Return a formatted string of all authors/creators."""
        if not self.authors:
            return "Unknown"
        return ", ".join(author.name for author in self.authors)
