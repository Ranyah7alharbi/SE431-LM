"""
SE431 - Phase 3 - Refactoring
Service layer: business logic only. No SQL. No print().
Returns (success, message) tuples.
"""

from datetime import datetime, timedelta

from policy import MAX_BOOKS, LOAN_DAYS, MEMBER_ACTIVE, calculate_fine


class LibraryService:

    def __init__(self, repo):
        self.repo = repo

    # ══════════════════════════════════════════════════════
    # Borrow
    # R1: borrow() was long, so every check is now its own method.
    # Each check returns an error message, or None if it is OK.
    # ══════════════════════════════════════════════════════
    def borrow(self, member_id, book_id):
        error = self.check_member(member_id)
        if error:
            return False, error

        error = self.check_book(book_id)
        if error:
            return False, error

        error = self.check_limit(member_id)
        if error:
            return False, error

        copy_id = self.repo.find_available_copy(book_id)
        if copy_id is None:
            return False, "No copies available"

        due = self.create_loan(member_id, copy_id)
        return True, f"Borrowed copy #{copy_id}. Due: {due.date()}"

    def check_member(self, member_id):
        member = self.repo.find_member(member_id)
        if not member:
            return "Member not found"
        if member.status != MEMBER_ACTIVE:
            return "Member is not active"
        return None

    def check_book(self, book_id):
        book = self.repo.find_book(book_id)
        if not book:
            return "Book not found"
        return None

    def check_limit(self, member_id):
        if self.repo.count_active_loans(member_id) >= MAX_BOOKS:
            return "Borrowing limit reached"
        return None

    def create_loan(self, member_id, copy_id):
        today = datetime.now()
        due = today + timedelta(days=LOAN_DAYS)
        self.repo.borrow_copy(member_id, copy_id,
                              today.isoformat(), due.isoformat())
        return due

    # ══════════════════════════════════════════════════════
    # Return
    # ══════════════════════════════════════════════════════
    def return_book(self, member_id, book_id):
        loan = self.repo.find_active_loan(member_id, book_id)
        if not loan:
            return False, "Active loan not found"

        due = datetime.fromisoformat(loan.due_date)
        fine = calculate_fine(due, datetime.now())

        self.repo.return_copy(loan.id, loan.copy_id)

        msg = f"Copy #{loan.copy_id} returned"
        if fine:
            msg += f" — Fine: {fine}"
        return True, msg

    # ══════════════════════════════════════════════════════
    # Search
    # ══════════════════════════════════════════════════════
    def search_books(self, text):
        return self.repo.search_books(text)
