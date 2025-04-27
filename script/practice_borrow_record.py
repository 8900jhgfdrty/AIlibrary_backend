# -*- coding: utf-8 -*-
"""
@File: practice_borrow_record.py
@author: Lu Yingjie
@time: April 10, 2025 14:41
Generate 100 BorrowRecord entries for testing.
"""
import os
import django
import random
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from api.models import BorrowRecord, User, Book

# Configure Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()

def generate_borrow_records():
    """
    Insert 100 BorrowRecord entries with randomized data.
    """
    # Retrieve all users and books
    users = list(User.objects.all())
    books = list(Book.objects.all())

    if not users or not books:
        raise ValueError("Ensure there are users and books in the database before generating records.")

    borrow_records = []
    for _ in range(100):
        user = random.choice(users)
        book = random.choice(books)
        status = random.choice(['borrowed', 'returned'])

        # Random borrow date within the past year
        borrow_date = make_aware(datetime.now() - timedelta(days=random.randint(0, 365)))

        # If returned, generate a return date after borrow
        return_date = None
        if status == 'returned':
            return_date = borrow_date + timedelta(days=random.randint(1, 30))

        borrow_records.append(
            BorrowRecord(
                user=user,
                book=book,
                borrow_date=borrow_date,
                return_date=return_date,
                status=status
            )
        )

    # Bulk create records for efficiency
    BorrowRecord.objects.bulk_create(borrow_records)
    print("Successfully inserted 100 BorrowRecord entries!")

if __name__ == '__main__':
    generate_borrow_records()
