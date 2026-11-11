"""
SE431 - Phase 2 - MR-02
Service layer: business logic only. No SQL. No print().
Returns (success, message) tuples.
"""

from datetime import datetime, timedelta


MAX_BOOKS = 3
LOAN_DAYS = 14
FINE_RATE = 1


class LibraryService:

    def __init__(self, repo):
        self.repo = repo

    # ══════════════════════════════════════════════════════
    # Borrow
    # ══════════════════════════════════════════════════════
    def borrow(self, member_id, book_id):
        # 1. member exists & active
        member = self.repo.find_member(member_id)
        if not member:
            return False, "Member not found"
        if member["status"] != "ACTIVE":
            return False, "Member is not active"

        # 2. book exists
        book = self.repo.find_book(book_id)
        if not book:
            return False, "Book not found"

        # 3. borrow limit
        if self.repo.count_active_loans(member_id) >= MAX_BOOKS:
            return False, "Borrowing limit reached"

        # 4. available copy
        copy_id = self.repo.find_available_copy(book_id)
        if copy_id is None:
            return False, "No copies available"

        # 5. create loan + mark copy
        today = datetime.now()
        due = today + timedelta(days=LOAN_DAYS)
        self.repo.create_loan(member_id, copy_id,
                              today.isoformat(), due.isoformat())
        self.repo.mark_copy_borrowed(copy_id)

        return True, f"Borrowed copy #{copy_id}. Due: {due.date()}"

    # ══════════════════════════════════════════════════════
    # Return
    # ══════════════════════════════════════════════════════
    def return_book(self, member_id, book_id):
        loan = self.repo.find_active_loan(member_id, book_id)
        if not loan:
            return False, "Active loan not found"

        due = datetime.fromisoformat(loan["due_date"])
        late = (datetime.now() - due).days
        fine = late * FINE_RATE if late > 0 else 0

        self.repo.close_loan(loan["id"])
        self.repo.mark_copy_available(loan["copy_id"])

        msg = f"Copy #{loan['copy_id']} returned"
        if fine:
            msg += f" — Fine: {fine}"
        return True, msg

    # ══════════════════════════════════════════════════════
    # Search
    # ══════════════════════════════════════════════════════
    def search_books(self, text):
        return self.repo.search_books(text)