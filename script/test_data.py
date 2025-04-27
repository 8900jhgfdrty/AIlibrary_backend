# -*- coding: utf-8 -*-
"""
@File: test_data.py
author: Lu Yingjie
time: April 10, 2025 9:25
Generate popular test data entries for categories, authors, and books.
"""
import os
import django

# Configure Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()

from api.models import Category, Author, Book

def insert_test_data():
    print("Starting to insert test data...")

    # Insert category data
    categories = ["Fiction", "Science Fiction", "Mystery & Thriller", "Non-Fiction", "Fantasy"]
    category_objects = []
    for name in categories:
        category, created = Category.objects.get_or_create(name=name)
        category_objects.append(category)
        if created:
            print(f"Created category: {name}")

    # Insert author data
    authors = [
        "Colleen Hoover",    # Romance & Contemporary
        "Brandon Sanderson", # Epic Fantasy
        "Stephen King",      # Horror & Thriller
        "Margaret Atwood",   # Dystopian Fiction
        "Celeste Ng"         # Literary Fiction
    ]
    author_objects = []
    for name in authors:
        author, created = Author.objects.get_or_create(
            name=name,
            defaults={"bio": f"Biography of {name}"}
        )
        author_objects.append(author)
        if created:
            print(f"Created author: {name}")

    # Insert book data
    books = [
        {"title": "It Ends with Us",            "category": category_objects[0], "author": author_objects[0]},
        {"title": "Rhythm of War",               "category": category_objects[4], "author": author_objects[1]},
        {"title": "Project Hail Mary",           "category": category_objects[1], "author": author_objects[2]},
        {"title": "The Testaments",              "category": category_objects[0], "author": author_objects[3]},
        {"title": "Little Fires Everywhere",      "category": category_objects[0], "author": author_objects[4]},
        {"title": "The Midnight Library",         "category": category_objects[0], "author": author_objects[4]},
        {"title": "Dune",                         "category": category_objects[1], "author": author_objects[2]},
        {"title": "The Silent Patient",           "category": category_objects[2], "author": author_objects[3]},
        {"title": "Educated",                     "category": category_objects[3], "author": author_objects[4]},
        {"title": "Children of Time",             "category": category_objects[1], "author": author_objects[1]},
    ]

    for book_data in books:
        book, created = Book.objects.get_or_create(
            title=book_data["title"],
            defaults={
                "category": book_data["category"],
                "author": book_data["author"],
                "description": f"Description of '{book_data['title']}'", 
                "is_available": True,
            }
        )
        if created:
            print(f"Created book: {book_data['title']}")

    print("Test data insertion complete!")

if __name__ == "__main__":
    insert_test_data()
