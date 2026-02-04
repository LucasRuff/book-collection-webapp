"""Generate a copy-paste-able reading list and save to reading_list.txt."""
import os
from app import app, db
from models import Book

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), 'reading_list.txt')

def format_authors(book):
    if not book.authors:
        return "Unknown"
    return ", ".join(a.name for a in book.authors)

def format_book_list(books, header):
    if not books:
        return ""
    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append(f"{header} ({len(books)} books)")
    lines.append('=' * 60)
    for book in sorted(books, key=lambda b: b.title):
        authors = format_authors(book)
        lines.append(f"• {book.title} — {authors}")
    return "\n".join(lines)

with app.app_context():
    # Exclude reference, to_work (textbooks), and coffee_table
    excluded_statuses = ['reference', 'to_work', 'coffee_table']
    
    books = Book.query.filter(
        ~Book.reading_status.in_(excluded_statuses)
    ).all()
    
    read_books = [b for b in books if b.reading_status == 'read']
    in_progress = [b for b in books if b.reading_status == 'in_progress']
    to_read = [b for b in books if b.reading_status == 'to_read']
    
    output = []
    output.append(format_book_list(read_books, "BOOKS I'VE READ"))
    output.append(format_book_list(in_progress, "CURRENTLY READING"))
    output.append(format_book_list(to_read, "TO BE READ"))
    
    content = "\n".join(filter(None, output))
    
    # Print to console
    print(content)
    
    # Write to file
    with open(OUTPUT_FILE, 'w') as f:
        f.write(content)
    
    print(f"\n\nSaved to {OUTPUT_FILE}")
