from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Book, Author, Publisher, ComicSeries, ComicIssue, ReadingQueue
from forms import BookForm, AuthorForm, PublisherForm, ComicSeriesForm, ComicIssueForm, QuickAddIssuesForm, SearchForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'CHANGE_ME_SET_SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///books.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


def auto_queue_book(book):
    """Add a book to the reading queue for its preferred format.
    
    Only queues if book has to_read or in_progress status.
    Format priority: physical > ebook > audiobook.
    Only uses ebook queue if no physical copy; only uses audiobook queue if that's the only format.
    """
    if book.reading_status not in ('to_read', 'in_progress'):
        return
    
    formats = book.formats_list
    
    # Determine the single queue format based on priority
    if 'physical' in formats:
        queue_format = 'physical'
    elif 'ebook' in formats:
        queue_format = 'ebook'
    elif 'audiobook' in formats:
        queue_format = 'audiobook'
    else:
        return  # No valid format
    
    # Check if already in queue for this format
    existing = ReadingQueue.query.filter_by(book_id=book.id, queue_format=queue_format).first()
    if existing:
        return
    
    # Find the last position in this format's queue
    last_entry = ReadingQueue.query.filter_by(queue_format=queue_format).order_by(ReadingQueue.position.desc()).first()
    next_position = (last_entry.position + 1) if last_entry else 1
    
    queue_entry = ReadingQueue(book_id=book.id, queue_format=queue_format, position=next_position)
    db.session.add(queue_entry)


@app.route('/')
def index():
    """Home page showing all books with search/filter capabilities."""
    from models import READING_STATUS_CHOICES 
    
    search_form = SearchForm(request.args, meta={'csrf': False})
    query = Book.query
    
    # Search by title, author, or publisher
    search_query = request.args.get('query', '').strip()
    if search_query:
        query = query.filter(
            db.or_(
                Book.title.ilike(f'%{search_query}%'),
                Book.authors.any(Author.name.ilike(f'%{search_query}%')),
                Book.publisher.has(Publisher.name.ilike(f'%{search_query}%'))
            )
        )
    
    # Filter by reading status
    status_filter = request.args.get('status_filter')
    if status_filter:
        query = query.filter(Book.reading_status == status_filter)
    
    # Filter by whether book has a publisher (personal vs textbook)
    collection_filter = request.args.get('collection')
    if collection_filter == 'personal':
        query = query.filter(Book.publisher_id.isnot(None))
    elif collection_filter == 'textbooks':
        query = query.filter(Book.publisher_id.is_(None))
    
    # Filter by language
    language_filter = request.args.get('language')
    if language_filter:
        query = query.filter(Book.language == language_filter)
    
    # Sorting
    sort_by = request.args.get('sort', 'title')
    sort_order = request.args.get('order', 'asc')
    
    if sort_by == 'title':
        order_col = Book.title
    elif sort_by == 'year':
        order_col = Book.publication_year
    elif sort_by == 'author':
        # Sort by first author name - requires a subquery or we just use title as fallback
        order_col = Book.title  # Fallback, proper author sort is complex
    elif sort_by == 'status':
        order_col = Book.reading_status
    else:
        order_col = Book.title
    
    if sort_order == 'desc':
        order_col = order_col.desc()
    
    books = query.order_by(order_col).all()
    
    # Get statistics
    total_books = Book.query.count()
    read_books = Book.query.filter_by(reading_status='read').count()
    total_authors = Author.query.count()
    total_publishers = Publisher.query.count()
    
    # Get counts by status for the filter UI
    status_counts = {}
    for code, label in READING_STATUS_CHOICES:
        status_counts[code] = Book.query.filter_by(reading_status=code).count()
    
    # Get distinct languages for the filter dropdown
    languages = [r[0] for r in db.session.query(Book.language).distinct().order_by(Book.language).all() if r[0]]
    
    return render_template('index.html', 
                         books=books, 
                         search_form=search_form,
                         total_books=total_books,
                         read_books=read_books,
                         total_authors=total_authors,
                         total_publishers=total_publishers,
                         status_choices=READING_STATUS_CHOICES,
                         status_counts=status_counts,
                         languages=languages)


def parse_author_ids(author_ids_str):
    """Parse the author_ids hidden field value.
    Format: 'id1,id2,id3:::new_name1|||new_name2|||new_name3'
    Returns: (list of existing author ids, list of new author names)
    """
    if not author_ids_str:
        return [], []
    
    parts = author_ids_str.split(':::')
    existing_ids = []
    new_names = []
    
    if parts[0]:
        existing_ids = [int(x) for x in parts[0].split(',') if x.strip()]
    
    if len(parts) > 1 and parts[1]:
        new_names = [name.strip() for name in parts[1].split('|||') if name.strip()]
    
    return existing_ids, new_names


@app.route('/book/add', methods=['GET', 'POST'])
def add_book():
    """Add a new book."""
    form = BookForm()
    form.publisher.choices = [(0, '-- Select Publisher --')] + [(p.id, p.name) for p in Publisher.query.order_by(Publisher.name).all()]
    
    if form.validate_on_submit():
        # Handle publisher
        publisher_id = None
        if form.new_publisher.data:
            # Check if publisher already exists
            existing_pub = Publisher.query.filter(Publisher.name.ilike(form.new_publisher.data.strip())).first()
            if existing_pub:
                publisher_id = existing_pub.id
            else:
                new_pub = Publisher(name=form.new_publisher.data.strip())
                db.session.add(new_pub)
                db.session.flush()
                publisher_id = new_pub.id
        elif form.publisher.data and form.publisher.data != 0:
            publisher_id = form.publisher.data
        
        book = Book(
            title=form.title.data,
            publisher_id=publisher_id,
            publication_year=form.publication_year.data,
            isbn=form.isbn.data or None,
            reading_status=form.reading_status.data,
            ownership_status=form.ownership_status.data,
            formats=','.join(form.formats.data) if form.formats.data else 'physical',
            language=form.language.data or 'English',
            notes=form.notes.data or None
        )
        
        # Parse authors from the new search-and-add field
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        # Add existing authors
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            book.authors.extend(selected_authors)
        
        # Add new authors
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in book.authors:
                    book.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                book.authors.append(new_author)
        
        db.session.add(book)
        db.session.flush()  # Get the book ID before queuing
        auto_queue_book(book)
        db.session.commit()
        flash(f'Book "{book.title}" added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('book_form.html', form=form, title='Add New Book')


@app.route('/book/<int:id>/edit', methods=['GET', 'POST'])
def edit_book(id):
    """Edit an existing book."""
    book = Book.query.get_or_404(id)
    form = BookForm(obj=book)
    form.publisher.choices = [(0, '-- Select Publisher --')] + [(p.id, p.name) for p in Publisher.query.order_by(Publisher.name).all()]
    
    if request.method == 'GET':
        form.publisher.data = book.publisher_id if book.publisher_id else 0
        form.formats.data = book.formats_list
    
    if form.validate_on_submit():
        book.title = form.title.data
        
        # Handle publisher
        if form.new_publisher.data:
            existing_pub = Publisher.query.filter(Publisher.name.ilike(form.new_publisher.data.strip())).first()
            if existing_pub:
                book.publisher_id = existing_pub.id
            else:
                new_pub = Publisher(name=form.new_publisher.data.strip())
                db.session.add(new_pub)
                db.session.flush()
                book.publisher_id = new_pub.id
        elif form.publisher.data and form.publisher.data != 0:
            book.publisher_id = form.publisher.data
        else:
            book.publisher_id = None
        
        book.publication_year = form.publication_year.data
        book.isbn = form.isbn.data or None
        book.reading_status = form.reading_status.data
        book.ownership_status = form.ownership_status.data
        book.formats = ','.join(form.formats.data) if form.formats.data else 'physical'
        book.language = form.language.data or 'English'
        book.notes = form.notes.data or None
        
        # Update authors from the new search-and-add field
        book.authors.clear()
        
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            book.authors.extend(selected_authors)
        
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in book.authors:
                    book.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                book.authors.append(new_author)
        
        auto_queue_book(book)
        db.session.commit()
        flash(f'Book "{book.title}" updated successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('book_form.html', form=form, title='Edit Book', book=book)


@app.route('/book/<int:id>/delete', methods=['POST'])
def delete_book(id):
    """Delete a book."""
    book = Book.query.get_or_404(id)
    title = book.title
    db.session.delete(book)
    db.session.commit()
    flash(f'Book "{title}" deleted.', 'info')
    return redirect(url_for('index'))


@app.route('/book/<int:id>/toggle-read', methods=['POST'])
def toggle_read(id):
    """Toggle between read and to_read status."""
    book = Book.query.get_or_404(id)
    if book.reading_status == 'read':
        book.reading_status = 'to_read'
        status = 'To Be Read'
    else:
        book.reading_status = 'read'
        status = 'Read'
    db.session.commit()
    flash(f'Marked "{book.title}" as {status}.', 'success')
    return redirect(request.referrer or url_for('index'))


@app.route('/authors')
def authors():
    """List all authors."""
    sort = request.args.get('sort', 'name')
    all_authors = Author.query.all()
    
    if sort == 'books':
        all_authors.sort(key=lambda a: len(a.books), reverse=True)
    elif sort == 'comics':
        all_authors.sort(key=lambda a: len(a.comic_issues), reverse=True)
    elif sort == 'total':
        all_authors.sort(key=lambda a: len(a.books) + len(a.comic_issues), reverse=True)
    else:
        all_authors.sort(key=lambda a: a.name.lower())
    
    return render_template('authors.html', authors=all_authors, current_sort=sort)


@app.route('/author/add', methods=['GET', 'POST'])
def add_author():
    """Add a new author."""
    form = AuthorForm()
    
    if form.validate_on_submit():
        # Check if author already exists
        existing = Author.query.filter(Author.name.ilike(form.name.data)).first()
        if existing:
            flash(f'Author "{existing.name}" already exists!', 'warning')
            return redirect(url_for('authors'))
        
        author = Author(name=form.name.data)
        db.session.add(author)
        db.session.commit()
        flash(f'Author "{author.name}" added successfully!', 'success')
        return redirect(url_for('authors'))
    
    return render_template('author_form.html', form=form, title='Add New Author')


@app.route('/author/<int:id>')
def view_author(id):
    """View author details."""
    author = Author.query.get_or_404(id)
    return render_template('author_detail.html', author=author)


@app.route('/author/<int:id>/edit', methods=['GET', 'POST'])
def edit_author(id):
    """Edit an existing author."""
    author = Author.query.get_or_404(id)
    form = AuthorForm(obj=author)
    
    if form.validate_on_submit():
        author.name = form.name.data
        db.session.commit()
        flash(f'Author "{author.name}" updated successfully!', 'success')
        return redirect(url_for('view_author', id=author.id))
    
    return render_template('author_form.html', form=form, title='Edit Author', author=author)


@app.route('/author/<int:id>/delete', methods=['POST'])
def delete_author(id):
    """Delete an author."""
    author = Author.query.get_or_404(id)
    name = author.name
    
    if author.books:
        flash(f'Cannot delete "{name}" - author has {len(author.books)} book(s) associated.', 'danger')
        return redirect(url_for('authors'))
    
    db.session.delete(author)
    db.session.commit()
    flash(f'Author "{name}" deleted.', 'info')
    return redirect(url_for('authors'))


@app.route('/book/<int:id>')
def view_book(id):
    """View book details."""
    book = Book.query.get_or_404(id)
    return render_template('book_detail.html', book=book)


@app.route('/publishers')
def publishers():
    """List all publishers."""
    sort = request.args.get('sort', 'name')
    all_publishers = Publisher.query.all()
    
    if sort == 'books':
        all_publishers.sort(key=lambda p: len(p.books), reverse=True)
    elif sort == 'comics':
        all_publishers.sort(key=lambda p: len(p.comic_series), reverse=True)
    elif sort == 'total':
        all_publishers.sort(key=lambda p: len(p.books) + len(p.comic_series), reverse=True)
    else:
        all_publishers.sort(key=lambda p: p.name.lower())
    
    return render_template('publishers.html', publishers=all_publishers, current_sort=sort)


@app.route('/publisher/add', methods=['GET', 'POST'])
def add_publisher():
    """Add a new publisher."""
    form = PublisherForm()
    
    if form.validate_on_submit():
        # Check if publisher already exists
        existing = Publisher.query.filter(Publisher.name.ilike(form.name.data)).first()
        if existing:
            flash(f'Publisher "{existing.name}" already exists!', 'warning')
            return redirect(url_for('publishers'))
        
        publisher = Publisher(name=form.name.data)
        db.session.add(publisher)
        db.session.commit()
        flash(f'Publisher "{publisher.name}" added successfully!', 'success')
        return redirect(url_for('publishers'))
    
    return render_template('publisher_form.html', form=form, title='Add New Publisher')


@app.route('/publisher/<int:id>')
def view_publisher(id):
    """View publisher details."""
    publisher = Publisher.query.get_or_404(id)
    return render_template('publisher_detail.html', publisher=publisher)


@app.route('/publisher/<int:id>/edit', methods=['GET', 'POST'])
def edit_publisher(id):
    """Edit an existing publisher."""
    publisher = Publisher.query.get_or_404(id)
    form = PublisherForm(obj=publisher)
    
    if form.validate_on_submit():
        publisher.name = form.name.data
        db.session.commit()
        flash(f'Publisher "{publisher.name}" updated successfully!', 'success')
        return redirect(url_for('view_publisher', id=publisher.id))
    
    return render_template('publisher_form.html', form=form, title='Edit Publisher', publisher=publisher)


@app.route('/publisher/<int:id>/delete', methods=['POST'])
def delete_publisher(id):
    """Delete a publisher."""
    publisher = Publisher.query.get_or_404(id)
    name = publisher.name
    
    if publisher.books or publisher.comic_series:
        count = len(publisher.books) + len(publisher.comic_series)
        flash(f'Cannot delete "{name}" - publisher has {count} book(s)/series associated.', 'danger')
        return redirect(url_for('publishers'))
    
    db.session.delete(publisher)
    db.session.commit()
    flash(f'Publisher "{name}" deleted.', 'info')
    return redirect(url_for('publishers'))


# ============== Comic Series Routes ==============

@app.route('/comics')
def comics():
    """List all comic series."""
    search_query = request.args.get('query', '').strip()
    query = ComicSeries.query
    
    if search_query:
        query = query.filter(
            db.or_(
                ComicSeries.name.ilike(f'%{search_query}%'),
                ComicSeries.publisher.has(Publisher.name.ilike(f'%{search_query}%'))
            )
        )
    
    all_series = query.order_by(ComicSeries.name).all()
    
    # Stats
    total_series = ComicSeries.query.count()
    total_issues = ComicIssue.query.count()
    read_issues = ComicIssue.query.filter_by(is_read=True).count()
    
    return render_template('comics.html', 
                         series_list=all_series,
                         total_series=total_series,
                         total_issues=total_issues,
                         read_issues=read_issues,
                         search_query=search_query)


@app.route('/comics/series/add', methods=['GET', 'POST'])
def add_comic_series():
    """Add a new comic series."""
    form = ComicSeriesForm()
    form.publisher.choices = [(0, '-- Select Publisher --')] + [(p.id, p.name) for p in Publisher.query.order_by(Publisher.name).all()]
    
    if form.validate_on_submit():
        # Handle publisher
        publisher_id = None
        if form.new_publisher.data:
            existing_pub = Publisher.query.filter(Publisher.name.ilike(form.new_publisher.data.strip())).first()
            if existing_pub:
                publisher_id = existing_pub.id
            else:
                new_pub = Publisher(name=form.new_publisher.data.strip())
                db.session.add(new_pub)
                db.session.flush()
                publisher_id = new_pub.id
        elif form.publisher.data and form.publisher.data != 0:
            publisher_id = form.publisher.data
        
        series = ComicSeries(
            name=form.name.data,
            volume=form.volume.data,
            start_year=form.start_year.data,
            publisher_id=publisher_id,
            notes=form.notes.data or None
        )
        
        # Parse authors from the search-and-add field
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            series.authors.extend(selected_authors)
        
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in series.authors:
                    series.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                series.authors.append(new_author)
        
        db.session.add(series)
        db.session.commit()
        flash(f'Series "{series.display_name}" added successfully!', 'success')
        return redirect(url_for('view_comic_series', id=series.id))
    
    return render_template('comic_series_form.html', form=form, title='Add New Comic Series')


@app.route('/comics/series/<int:id>')
def view_comic_series(id):
    """View a comic series and its issues."""
    series = ComicSeries.query.get_or_404(id)
    return render_template('comic_series_detail.html', series=series)


@app.route('/comics/series/<int:id>/edit', methods=['GET', 'POST'])
def edit_comic_series(id):
    """Edit a comic series."""
    series = ComicSeries.query.get_or_404(id)
    form = ComicSeriesForm(obj=series)
    form.publisher.choices = [(0, '-- Select Publisher --')] + [(p.id, p.name) for p in Publisher.query.order_by(Publisher.name).all()]
    
    if request.method == 'GET':
        form.publisher.data = series.publisher_id if series.publisher_id else 0
    
    if form.validate_on_submit():
        series.name = form.name.data
        series.volume = form.volume.data
        series.start_year = form.start_year.data
        series.notes = form.notes.data or None
        
        # Handle publisher
        if form.new_publisher.data:
            existing_pub = Publisher.query.filter(Publisher.name.ilike(form.new_publisher.data.strip())).first()
            if existing_pub:
                series.publisher_id = existing_pub.id
            else:
                new_pub = Publisher(name=form.new_publisher.data.strip())
                db.session.add(new_pub)
                db.session.flush()
                series.publisher_id = new_pub.id
        elif form.publisher.data and form.publisher.data != 0:
            series.publisher_id = form.publisher.data
        else:
            series.publisher_id = None
        
        # Update authors from the search-and-add field
        series.authors.clear()
        
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            series.authors.extend(selected_authors)
        
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in series.authors:
                    series.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                series.authors.append(new_author)
        
        db.session.commit()
        flash(f'Series "{series.display_name}" updated successfully!', 'success')
        return redirect(url_for('view_comic_series', id=series.id))
    
    return render_template('comic_series_form.html', form=form, title='Edit Comic Series', series=series)


@app.route('/comics/series/<int:id>/delete', methods=['POST'])
def delete_comic_series(id):
    """Delete a comic series and all its issues."""
    series = ComicSeries.query.get_or_404(id)
    name = series.display_name
    
    # Delete all issues first
    ComicIssue.query.filter_by(series_id=id).delete()
    db.session.delete(series)
    db.session.commit()
    flash(f'Series "{name}" and all its issues deleted.', 'info')
    return redirect(url_for('comics'))


# ============== Comic Issue Routes ==============

@app.route('/comics/issue/add', methods=['GET', 'POST'])
@app.route('/comics/series/<int:series_id>/issue/add', methods=['GET', 'POST'])
def add_comic_issue(series_id=None):
    """Add a new comic issue."""
    form = ComicIssueForm()
    form.series.choices = [(s.id, s.display_name) for s in ComicSeries.query.order_by(ComicSeries.name).all()]
    
    if series_id and request.method == 'GET':
        form.series.data = series_id
    
    if form.validate_on_submit():
        issue = ComicIssue(
            series_id=form.series.data,
            issue_number=form.issue_number.data,
            title=form.title.data or None,
            cover_date=form.cover_date.data or None,
            cover_variant=form.cover_variant.data or None,
            is_read=form.is_read.data,
            notes=form.notes.data or None
        )
        
        # Parse authors from the search-and-add field
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            issue.authors.extend(selected_authors)
        
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in issue.authors:
                    issue.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                issue.authors.append(new_author)
        
        db.session.add(issue)
        
        # Also add any new authors to the series
        series = ComicSeries.query.get(form.series.data)
        if series:
            for author in issue.authors:
                if author not in series.authors:
                    series.authors.append(author)
        
        db.session.commit()
        flash(f'Issue "{issue.display_name}" added successfully!', 'success')
        return redirect(url_for('view_comic_series', id=issue.series_id))
    
    return render_template('comic_issue_form.html', form=form, title='Add New Issue')


@app.route('/comics/issue/<int:id>/edit', methods=['GET', 'POST'])
def edit_comic_issue(id):
    """Edit a comic issue."""
    issue = ComicIssue.query.get_or_404(id)
    form = ComicIssueForm(obj=issue)
    form.series.choices = [(s.id, s.display_name) for s in ComicSeries.query.order_by(ComicSeries.name).all()]
    
    if form.validate_on_submit():
        issue.series_id = form.series.data
        issue.issue_number = form.issue_number.data
        issue.title = form.title.data or None
        issue.cover_date = form.cover_date.data or None
        issue.cover_variant = form.cover_variant.data or None
        issue.is_read = form.is_read.data
        issue.notes = form.notes.data or None
        
        # Update authors from the search-and-add field
        issue.authors.clear()
        
        author_ids_str = request.form.get('author_ids', '')
        existing_ids, new_names = parse_author_ids(author_ids_str)
        
        if existing_ids:
            selected_authors = Author.query.filter(Author.id.in_(existing_ids)).all()
            issue.authors.extend(selected_authors)
        
        for name in new_names:
            existing = Author.query.filter(Author.name.ilike(name)).first()
            if existing:
                if existing not in issue.authors:
                    issue.authors.append(existing)
            else:
                new_author = Author(name=name)
                db.session.add(new_author)
                issue.authors.append(new_author)
        
        db.session.commit()
        flash(f'Issue "{issue.display_name}" updated successfully!', 'success')
        return redirect(url_for('view_comic_series', id=issue.series_id))
    
    return render_template('comic_issue_form.html', form=form, title='Edit Issue', issue=issue)


@app.route('/comics/issue/<int:id>/delete', methods=['POST'])
def delete_comic_issue(id):
    """Delete a comic issue."""
    issue = ComicIssue.query.get_or_404(id)
    series_id = issue.series_id
    name = issue.display_name
    db.session.delete(issue)
    db.session.commit()
    flash(f'Issue "{name}" deleted.', 'info')
    return redirect(url_for('view_comic_series', id=series_id))


@app.route('/comics/issue/<int:id>/toggle-read', methods=['POST'])
def toggle_issue_read(id):
    """Toggle the read status of an issue."""
    issue = ComicIssue.query.get_or_404(id)
    issue.is_read = not issue.is_read
    db.session.commit()
    status = "read" if issue.is_read else "unread"
    flash(f'Marked "{issue.display_name}" as {status}.', 'success')
    return redirect(request.referrer or url_for('view_comic_series', id=issue.series_id))


@app.route('/comics/series/<int:series_id>/quick-add', methods=['GET', 'POST'])
def quick_add_issues(series_id):
    """Quickly add multiple issues to a series."""
    series = ComicSeries.query.get_or_404(series_id)
    form = QuickAddIssuesForm()
    form.series.choices = [(series.id, series.display_name)]
    form.series.data = series.id
    
    if form.validate_on_submit():
        # Parse issue numbers (supports: 1,2,3 or 1-5 or 1,3-5,7)
        issue_numbers = []
        parts = form.issue_numbers.data.replace(' ', '').split(',')
        for part in parts:
            if '-' in part:
                try:
                    start, end = part.split('-')
                    issue_numbers.extend(range(int(start), int(end) + 1))
                except:
                    pass
            else:
                try:
                    issue_numbers.append(float(part))
                except:
                    pass
        
        # Add issues that don't already exist
        existing = {i.issue_number for i in series.issues}
        added = 0
        
        # Get selected author IDs from checkboxes
        selected_author_ids = request.form.getlist('author_ids', type=int)
        selected_authors = Author.query.filter(Author.id.in_(selected_author_ids)).all() if selected_author_ids else []
        
        for num in issue_numbers:
            if num not in existing:
                issue = ComicIssue(series_id=series.id, issue_number=num)
                # Add only selected authors
                for author in selected_authors:
                    issue.authors.append(author)
                db.session.add(issue)
                added += 1
        
        db.session.commit()
        if added:
            flash(f'Added {added} issue(s) to "{series.display_name}".', 'success')
        else:
            flash('No new issues added (all already exist).', 'info')
        return redirect(url_for('view_comic_series', id=series.id))
    
    return render_template('quick_add_issues.html', form=form, series=series)


# ============== API Routes ==============

@app.route('/api/authors/search')
def api_search_authors():
    """Search authors by name for autocomplete."""
    query = request.args.get('q', '').strip()
    if len(query) < 1:
        return jsonify([])
    
    authors = Author.query.filter(
        Author.name.ilike(f'%{query}%')
    ).order_by(Author.name).limit(10).all()
    
    return jsonify([{'id': a.id, 'name': a.name} for a in authors])


@app.route('/api/authors/<int:id>')
def api_get_author(id):
    """Get a single author by ID."""
    author = Author.query.get_or_404(id)
    return jsonify({'id': author.id, 'name': author.name})


@app.route('/api/series/<int:id>/authors')
def api_get_series_authors(id):
    """Get authors for a comic series."""
    series = ComicSeries.query.get_or_404(id)
    return jsonify([{'id': a.id, 'name': a.name} for a in series.authors])


# =============================================================================
# Reading Queue API
# =============================================================================

@app.route('/api/reading-queue')
def get_reading_queue():
    """Get the top N books from each format queue."""
    limit = request.args.get('limit', 3, type=int)
    
    result = {}
    for queue_format in ['physical', 'ebook', 'audiobook']:
        queue_items = ReadingQueue.query.filter_by(queue_format=queue_format)\
            .order_by(ReadingQueue.position).limit(limit).all()
        
        result[queue_format] = []
        for item in queue_items:
            book = item.book
            result[queue_format].append({
                'id': book.id,
                'title': book.title,
                'authors': book.authors_display,
                'position': item.position
            })
    
    return jsonify(result)


@app.route('/api/reading-queue/<int:book_id>/finish', methods=['POST'])
def finish_book_from_queue(book_id):
    """Mark a book as read and remove from queue."""
    book = Book.query.get_or_404(book_id)
    queue_format = request.args.get('format', 'physical')
    queue_entry = ReadingQueue.query.filter_by(book_id=book_id, queue_format=queue_format).first()
    
    if queue_entry:
        removed_position = queue_entry.position
        db.session.delete(queue_entry)
        
        # Reorder remaining items in this format's queue
        ReadingQueue.query.filter(
            ReadingQueue.queue_format == queue_format,
            ReadingQueue.position > removed_position
        ).update({ReadingQueue.position: ReadingQueue.position - 1})
    
    book.reading_status = 'read'
    db.session.commit()
    
    flash(f'Finished "{book.title}"! Great job.', 'success')
    return jsonify({'success': True, 'message': f'Marked "{book.title}" as read'})


@app.route('/api/reading-queue/<int:book_id>/dnf', methods=['POST'])
def dnf_book_from_queue(book_id):
    """Mark a book as DNF and remove from queue."""
    book = Book.query.get_or_404(book_id)
    queue_format = request.args.get('format', 'physical')
    queue_entry = ReadingQueue.query.filter_by(book_id=book_id, queue_format=queue_format).first()
    
    if queue_entry:
        removed_position = queue_entry.position
        db.session.delete(queue_entry)
        
        # Reorder remaining items in this format's queue
        ReadingQueue.query.filter(
            ReadingQueue.queue_format == queue_format,
            ReadingQueue.position > removed_position
        ).update({ReadingQueue.position: ReadingQueue.position - 1})
    
    book.reading_status = 'dnf'
    db.session.commit()
    
    flash(f'Marked "{book.title}" as DNF. Moving on.', 'info')
    return jsonify({'success': True, 'message': f'Marked "{book.title}" as DNF'})


@app.route('/api/reading-queue/<int:book_id>/skip', methods=['POST'])
def skip_book_in_queue(book_id):
    """Move a book to the end of the queue (skip for now)."""
    queue_format = request.args.get('format', 'physical')
    queue_entry = ReadingQueue.query.filter_by(book_id=book_id, queue_format=queue_format).first_or_404()
    
    old_position = queue_entry.position
    max_position = db.session.query(db.func.max(ReadingQueue.position))\
        .filter(ReadingQueue.queue_format == queue_format).scalar() or 0
    
    # Move all items after this one up by 1 in this format's queue
    ReadingQueue.query.filter(
        ReadingQueue.queue_format == queue_format,
        ReadingQueue.position > old_position
    ).update({ReadingQueue.position: ReadingQueue.position - 1})
    
    # Move this item to the end
    queue_entry.position = max_position
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'Moved "{queue_entry.book.title}" to end of queue'})


if __name__ == '__main__':
    debug_flag = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', '5000'))
    app.run(debug=debug_flag, host=host, port=port)
