# -*- coding: utf-8 -*-
"""
@File: insert_test_data.py
@author: Lu Yingjie
@time: April 08, 2025 10:43
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from django.contrib.auth.models import User as AuthUser
from api.models import Announcement, Book, BorrowRecord, Rating, User

class Command(BaseCommand):
    help = "Insert test data into the database and truncate existing data"

    def handle(self, *args, **options):
        # Truncate all table data
        self.truncate_tables()

        # Insert test data
        self.insert_users()
        self.insert_announcements()
        self.insert_books()
        self.insert_user_profiles()
        self.insert_borrow_records()
        self.insert_ratings()

        self.stdout.write(self.style.SUCCESS("Successfully inserted all test data!"))

    def truncate_tables(self):
        """
        Truncate all table data
        """
        models = [Announcement, Book, User, BorrowRecord, Rating, AuthUser]
        for model in models:
            model.objects.all().delete()
        self.stdout.write(self.style.WARNING("All tables have been truncated"))

    def insert_users(self):
        """
        Insert user data
        """
        users = []
        for i in range(1, 11):
            username = f"user{i}"
            email = f"user{i}@example.com"
            password = "123456"
            user, created = AuthUser.objects.get_or_create(username=username, email=email)
            if created:
                user.set_password(password)
                user.save()
            users.append(user)
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {len(users)} user records"))

    def insert_announcements(self):
        """
        Insert announcement data
        """
        announcements = [
            {"title": "Library Closure Notice", "content": "Due to a system upgrade, the library will be closed for one day this Friday."},
            {"title": "New Book Recommendation Event", "content": "A new book recommendation event will be held this Saturday. You’re welcome to join us."},
            {"title": "System Maintenance Announcement", "content": "The system will be under maintenance tonight. Please save your work in advance."},
            {"title": "Summer Opening Hours Adjustment", "content": "During the summer break, opening hours are adjusted to 9:00 AM–5:00 PM."},
            {"title": "Library Borrowing Policy Update", "content": "The new borrowing policy is now in effect. Please check the details."},
            {"title": "Reading Share Session Invitation", "content": "A reading share session on science fiction novels will be held this Sunday."},
            {"title": "Electronic Resources Usage Guide", "content": "How to use the library’s electronic resources? Click here for the guide."},
            {"title": "Weekend Special Event", "content": "There’s a special event this weekend. Stay tuned for details."},
            {"title": "Library Relocation Notice", "content": "The library will relocate to a new site next month. Please take note."},
            {"title": "Spring Reading Challenge", "content": "Join the Spring Reading Challenge and win wonderful prizes!"}
        ]
        for data in announcements:
            Announcement.objects.create(
                title=data["title"],
                content=data["content"],
                is_visible=random.choice([True, False]),
                published_at=now() - timedelta(days=random.randint(0, 30)),
            )
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {len(announcements)} announcement records"))

    def insert_books(self):
        """
        Insert book data
        """
        books = [
            {"title": "Python Programming: From Beginner to Practice", "author": "Eric Matthes", "category": "Programming", "isbn": "9787115428028"},
            {"title": "Computer Systems: A Programmer’s Perspective", "author": "Randal E. Bryant", "category": "Computer Science", "isbn": "9787111407010"},
            {"title": "Introduction to Algorithms", "author": "Thomas H. Cormen", "category": "Algorithms", "isbn": "9787111407027"},
            {"title": "Machine Learning", "author": "Zhi-Hua Zhou", "category": "Artificial Intelligence", "isbn": "9787302426544"},
            {"title": "Deep Learning", "author": "Ian Goodfellow", "category": "Artificial Intelligence", "isbn": "9787111592528"},
            {"title": "How to Win Friends and Influence People", "author": "Dale Carnegie", "category": "Psychology", "isbn": "9787506385266"},
            {"title": "The Little Prince", "author": "Antoine de Saint-Exupéry", "category": "Literature", "isbn": "9787544261085"},
            {"title": "Spring, Summer, Autumn, and Winter on White Deer Plain", "author": "Chen Zhongshi", "category": "Literature", "isbn": "9787020089536"},
            {"title": "Sapiens: A Brief History of Humankind", "author": "Yuval Noah Harari", "category": "History", "isbn": "9787508660752"},
            {"title": "Principles of Economics", "author": "Gregory Mankiw", "category": "Economics", "isbn": "9787302466582"},
        ]
        for data in books:
            Book.objects.create(
                title=data["title"],
                author=data["author"],
                category=data["category"],
                publish_date=now().date() - timedelta(days=random.randint(0, 365 * 5)),
                isbn=data["isbn"],
                description=f"This is a great book about {data['category']}.",
            )
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {len(books)} book records"))

    def insert_user_profiles(self):
        """
        Insert user profile data
        """
        for auth_user in AuthUser.objects.all():
            User.objects.get_or_create(
                user=auth_user,
                defaults={
                    "username": auth_user.username,
                    "password": "default_password",
                    "role": random.choice(['admin', 'user', 'root']),
                }
            )
        count = AuthUser.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {count} user profile records"))

    def insert_borrow_records(self):
        """
        Insert borrow record data
        """
        books_all = list(Book.objects.all())
        users = list(AuthUser.objects.all())
        for user in users:
            for _ in range(random.randint(1, 5)):
                book = random.choice(books_all)
                borrow_date = now() - timedelta(days=random.randint(0, 30))
                return_date = borrow_date + timedelta(days=random.randint(7, 30)) if random.random() > 0.5 else None
                BorrowRecord.objects.create(
                    user=user,
                    book=book,
                    borrow_date=borrow_date,
                    return_date=return_date,
                )
        total = BorrowRecord.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {total} borrow record(s)"))

    def insert_ratings(self):
        """
        Insert rating data
        """
        books_all = list(Book.objects.all())
        users = list(AuthUser.objects.all())
        for user in users:
            for book in random.sample(books_all, k=random.randint(1, 5)):
                score = random.randint(1, 5)
                Rating.objects.get_or_create(
                    user=user,
                    book=book,
                    score=score,
                )
        total = Rating.objects.count()
        self.stdout.write(self.style.SUCCESS(f"Successfully inserted {total} rating record(s)"))
