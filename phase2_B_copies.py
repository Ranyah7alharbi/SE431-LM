"""
SE431 - Phase 2 - MR-01 (Strategy B: Copy Entity)
Multiple copies via a dedicated book_copies table.
"""

import sqlite3
from datetime import datetime, timedelta

DB = "library_phase2B.db"
MAX_BOOKS = 3
LOAN_DAYS = 14
FINE_RATE = 1


# ══════════════════════════════════════════════════════════
# Setup — NEW SCHEMA
# ══════════════════════════════════════════════════════════
def setup():
    db = sqlite3.connect(DB)
    db.execute("PRAGMA foreign_keys = ON")
    c = db.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS members(
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT
        )
    """)

    # books: no availability here anymore
    c.execute("""
        CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY,
            title TEXT,
            author TEXT
        )
    """)

    # NEW: one row per physical copy
    c.execute("""
        CREATE TABLE IF NOT EXISTS book_copies(
            copy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            CHECK (status IN ('AVAILABLE','BORROWED','DAMAGED','LOST')),
            FOREIGN KEY(book_id) REFERENCES books(id)
        )
    """)

    # loans: points to copy_id instead of book_id
    c.execute("""
        CREATE TABLE IF NOT EXISTS loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT,
            copy_id INTEGER NOT NULL,
            borrow_date TEXT,
            due_date TEXT,
            returned INTEGER DEFAULT 0,
            FOREIGN KEY(copy_id) REFERENCES book_copies(copy_id),
            FOREIGN KEY(member_id) REFERENCES members(id)
        )
    """)

    db.commit()

    # Sample data
    c.execute("INSERT OR IGNORE INTO members VALUES ('S1','Ali','ACTIVE')")
    c.execute("INSERT OR IGNORE INTO members VALUES ('S2','Sara','ACTIVE')")
    c.execute("INSERT OR IGNORE INTO members VALUES ('S3','Omar','INACTIVE')")

    c.execute("INSERT OR IGNORE INTO books VALUES (1,'Clean Code','Robert Martin')")
    c.execute("INSERT OR IGNORE INTO books VALUES (2,'Refactoring','Martin Fowler')")
    c.execute("INSERT OR IGNORE INTO books VALUES (3,'Design Patterns','Gamma et al.')")

    # Create copies: 3 x Clean Code, 2 x Refactoring, 1 x Design Patterns
    _ensure_copies(c, 1, 3)
    _ensure_copies(c, 2, 2)
    _ensure_copies(c, 3, 1)

    db.commit()
    return db


def _ensure_copies(cursor, book_id, count):
    """Create N copies for a book if not enough exist."""
    cursor.execute(
        "SELECT COUNT(*) FROM book_copies WHERE book_id=?", (book_id,)
    )
    existing = cursor.fetchone()[0]
    for _ in range(count - existing):
        cursor.execute(
            "INSERT INTO book_copies(book_id,status) VALUES(?, 'AVAILABLE')",
            (book_id,)
        )


# ══════════════════════════════════════════════════════════
# Search
# ══════════════════════════════════════════════════════════
def search_books(db, text):
    c = db.cursor()
    pat = "%" + text + "%"

    c.execute(
        """SELECT b.id, b.title, b.author,
                  COUNT(bc.copy_id) AS total,
                  SUM(CASE WHEN bc.status='AVAILABLE' THEN 1 ELSE 0 END) AS avail
           FROM books b
           LEFT JOIN book_copies bc ON bc.book_id = b.id
           WHERE b.title LIKE ? OR b.author LIKE ?
           GROUP BY b.id""",
        (pat, pat)
    )

    rows = c.fetchall()
    if not rows:
        print("No books found.")
        return rows

    for row in rows:
        avail = row[4] or 0
        print(f"  [{row[0]}] {row[1]} - {row[2]}  Available: {avail}/{row[3]}")

    return rows


# ══════════════════════════════════════════════════════════
# Borrow
# ══════════════════════════════════════════════════════════
def borrow(db, member_id, book_id):
    c = db.cursor()

    # 1. member check
    c.execute("SELECT id,status FROM members WHERE id=?", (member_id,))
    member = c.fetchone()
    if not member:
        print("Member not found")
        return False
    if member[1] != "ACTIVE":
        print("Member is not active")
        return False

    # 2. book exists?
    c.execute("SELECT id,title FROM books WHERE id=?", (book_id,))
    book = c.fetchone()
    if not book:
        print("Book not found")
        return False

    # 3. limit check
    c.execute(
        "SELECT COUNT(*) FROM loans WHERE member_id=? AND returned=0",
        (member_id,)
    )
    if c.fetchone()[0] >= MAX_BOOKS:
        print("Borrowing limit reached")
        return False

    # 4. find an AVAILABLE copy (FIFO)
    c.execute(
        """SELECT copy_id FROM book_copies
           WHERE book_id=? AND status='AVAILABLE'
           ORDER BY copy_id LIMIT 1""",
        (book_id,)
    )
    row = c.fetchone()
    if not row:
        print("No copies available")
        return False

    copy_id = row[0]

    # 5. create loan + mark copy BORROWED
    today = datetime.now()
    due = today + timedelta(days=LOAN_DAYS)

    c.execute(
        """INSERT INTO loans(member_id,copy_id,borrow_date,due_date,returned)
           VALUES(?,?,?,?,0)""",
        (member_id, copy_id, today.isoformat(), due.isoformat())
    )

    c.execute(
        "UPDATE book_copies SET status='BORROWED' WHERE copy_id=?",
        (copy_id,)
    )

    db.commit()

    print(f"Borrowed copy #{copy_id}. Due: {due.date()}")
    return True


# ══════════════════════════════════════════════════════════
# Return
# ══════════════════════════════════════════════════════════
def return_book(db, member_id, book_id):
    c = db.cursor()

    # find active loan for ANY copy of this book
    c.execute(
        """SELECT l.id, l.due_date, l.copy_id
           FROM loans l
           JOIN book_copies bc ON bc.copy_id = l.copy_id
           WHERE l.member_id=? AND bc.book_id=? AND l.returned=0
           LIMIT 1""",
        (member_id, book_id)
    )
    loan = c.fetchone()
    if not loan:
        print("Active loan not found")
        return False

    loan_id, due_str, copy_id = loan
    due = datetime.fromisoformat(due_str)
    late = (datetime.now() - due).days
    fine = late * FINE_RATE if late > 0 else 0

    # close loan + mark copy AVAILABLE
    c.execute("UPDATE loans SET returned=1 WHERE id=?", (loan_id,))
    c.execute(
        "UPDATE book_copies SET status='AVAILABLE' WHERE copy_id=?",
        (copy_id,)
    )

    db.commit()

    print(f"Copy #{copy_id} returned")
    if fine:
        print(f"Fine: {fine}")

    return True


# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════
def main():
    db = setup()

    while True:
        print("\n════════ LIBRARY (Strategy B) ════════")
        print("1. Search")
        print("2. Borrow")
        print("3. Return")
        print("4. Exit")

        choice = input("Choice: ").strip()

        if choice == "1":
            text = input("Search text: ")
            search_books(db, text)

        elif choice == "2":
            member = input("Member ID: ").strip()
            try:
                book = int(input("Book ID: "))
            except ValueError:
                print("Invalid book ID")
                continue
            borrow(db, member, book)

        elif choice == "3":
            member = input("Member ID: ").strip()
            try:
                book = int(input("Book ID: "))
            except ValueError:
                print("Invalid book ID")
                continue
            return_book(db, member, book)

        elif choice == "4":
            db.close()
            print("Goodbye.")
            break

        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()