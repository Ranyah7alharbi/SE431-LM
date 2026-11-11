"""
SE431 - Phase 2 - MR-01 (Strategy A: Counters)
Multiple copies per book using counters
"""

import sqlite3
from datetime import datetime, timedelta

DB = "library_phase2A.db"
MAX_BOOKS = 3
LOAN_DAYS = 14
FINE_RATE = 1


# ══════════════════════════════════════════════════════════
# Setup — CHANGED (MR-01)
# ══════════════════════════════════════════════════════════
def setup():
    db = sqlite3.connect(DB)
    c = db.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS members(
            id TEXT PRIMARY KEY,
            name TEXT,
            status TEXT
        )
    """)

    # CHANGED: available INTEGER → total_copies + available_copies
    c.execute("""
        CREATE TABLE IF NOT EXISTS books(
            id INTEGER PRIMARY KEY,
            title TEXT,
            author TEXT,
            total_copies     INTEGER NOT NULL DEFAULT 1,
            available_copies INTEGER NOT NULL DEFAULT 1,
            CHECK (available_copies >= 0),
            CHECK (available_copies <= total_copies)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_id TEXT,
            book_id INTEGER,
            borrow_date TEXT,
            due_date TEXT,
            returned INTEGER
        )
    """)

    db.commit()

    # Sample data
    c.execute("INSERT OR IGNORE INTO members VALUES ('S1','Ali','ACTIVE')")
    c.execute("INSERT OR IGNORE INTO members VALUES ('S2','Sara','ACTIVE')")
    c.execute("INSERT OR IGNORE INTO members VALUES ('S3','Omar','INACTIVE')")

    # CHANGED: multiple copies per book
    c.execute("INSERT OR IGNORE INTO books VALUES (1,'Clean Code','Robert Martin',3,3)")
    c.execute("INSERT OR IGNORE INTO books VALUES (2,'Refactoring','Martin Fowler',2,2)")
    c.execute("INSERT OR IGNORE INTO books VALUES (3,'Design Patterns','Gamma et al.',1,1)")

    db.commit()
    return db


# ══════════════════════════════════════════════════════════
# Search — CHANGED (display 3/5 instead of True/False)
# ══════════════════════════════════════════════════════════
def search_books(db, text):
    c = db.cursor()
    pat = "%" + text + "%"

    c.execute(
        """SELECT id, title, author, total_copies, available_copies
           FROM books
           WHERE title LIKE ? OR author LIKE ?""",
        (pat, pat)
    )

    rows = c.fetchall()

    if not rows:
        print("No books found.")
        return rows

    for row in rows:
        print(f"  [{row[0]}] {row[1]} - {row[2]}  "
              f"Available: {row[4]}/{row[3]}")

    return rows


# ══════════════════════════════════════════════════════════
# Borrow — CHANGED (core logic)
# ══════════════════════════════════════════════════════════
def borrow(db, member_id, book_id):
    c = db.cursor()

    # 1. member check (unchanged)
    c.execute("SELECT id,status FROM members WHERE id=?", (member_id,))
    member = c.fetchone()
    if not member:
        print("Member not found")
        return False
    if member[1] != "ACTIVE":
        print("Member is not active")
        return False

    # 2. book check — CHANGED
    c.execute(
        "SELECT id,title,total_copies,available_copies FROM books WHERE id=?",
        (book_id,)
    )
    book = c.fetchone()
    if not book:
        print("Book not found")
        return False

    # CHANGED: check available_copies instead of binary flag
    if book[3] <= 0:
        print("No copies available")
        return False

    # 3. limit check (unchanged)
    c.execute(
        "SELECT COUNT(*) FROM loans WHERE member_id=? AND returned=0",
        (member_id,)
    )
    if c.fetchone()[0] >= MAX_BOOKS:
        print("Borrowing limit reached")
        return False

    # 4. create loan (unchanged)
    today = datetime.now()
    due = today + timedelta(days=LOAN_DAYS)

    c.execute(
        """INSERT INTO loans(member_id,book_id,borrow_date,due_date,returned)
           VALUES(?,?,?,?,0)""",
        (member_id, book_id, today.isoformat(), due.isoformat())
    )

    # CHANGED: decrement instead of set to 0
    c.execute(
        """UPDATE books
           SET available_copies = available_copies - 1
           WHERE id=? AND available_copies > 0""",
        (book_id,)
    )

    db.commit()

    remaining = book[3] - 1
    print(f"Book borrowed. Remaining copies: {remaining}. Due: {due.date()}")
    return True


# ══════════════════════════════════════════════════════════
# Return — CHANGED (increment instead of set to 1)
# ══════════════════════════════════════════════════════════
def return_book(db, member_id, book_id):
    c = db.cursor()

    c.execute(
        """SELECT id,due_date FROM loans
           WHERE member_id=? AND book_id=? AND returned=0""",
        (member_id, book_id)
    )

    loan = c.fetchone()
    if not loan:
        print("Active loan not found")
        return False

    loan_id = loan[0]
    due = datetime.fromisoformat(loan[1])
    today = datetime.now()

    late = (today - due).days
    fine = late * FINE_RATE if late > 0 else 0

    c.execute("UPDATE loans SET returned=1 WHERE id=?", (loan_id,))

    # CHANGED: increment instead of set to 1
    c.execute(
        """UPDATE books
           SET available_copies = available_copies + 1
           WHERE id=? AND available_copies < total_copies""",
        (book_id,)
    )

    db.commit()

    print("Book returned")
    if fine:
        print(f"Fine: {fine}")

    return True


# ══════════════════════════════════════════════════════════
# Main (unchanged)
# ══════════════════════════════════════════════════════════
def main():
    db = setup()

    while True:
        print("\n════════ LIBRARY (Strategy A) ════════")
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