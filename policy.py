"""
SE431 - Phase 3 - Refactoring
Library rules in one place.
"""

# Borrowing rules
MAX_BOOKS = 3
LOAN_DAYS = 14
FINE_RATE = 1

# R2: status values (before they were written as text in many places)
MEMBER_ACTIVE = "ACTIVE"

COPY_AVAILABLE = "AVAILABLE"
COPY_BORROWED = "BORROWED"


# R4: fine calculation (before it was inside return_book)
def calculate_fine(due_date, return_date):
    days_late = (return_date - due_date).days
    if days_late > 0:
        return days_late * FINE_RATE
    return 0
