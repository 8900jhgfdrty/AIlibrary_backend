# -*- coding: utf-8 -*-
"""
@File: suanfa.py
@author: Lu Yingjie
@time: April 10, 2025 14:05
Algorithm utilities for library recommendations.
"""
import os
import django
import random
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from api.models import Recommendation, User, Book

# Configure Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()

def generate_recommendations():
    """
    Insert 100 Recommendation entries with randomized data.
    """
    # Retrieve all users and books
    users = list(User.objects.all())
    books = list(Book.objects.all())

    if not users or not books:
        raise ValueError("Ensure there are users and books in the database before generating recommendations.")

    recommendations = []
    for _ in range(100):
        user = random.choice(users)
        book = random.choice(books)
        # Random score between 1.0 and 5.0
        score = round(random.uniform(1.0, 5.0), 2)

        # Random creation timestamp within the past year
        created_at = make_aware(datetime.now() - timedelta(days=random.randint(0, 365)))

        recommendations.append(
            Recommendation(
                user=user,
                book=book,
                score=score,
                created_at=created_at
            )
        )

    # Bulk create for efficiency
    Recommendation.objects.bulk_create(recommendations)

    print("Successfully inserted 100 Recommendation entries!")

if __name__ == '__main__':
    generate_recommendations()
