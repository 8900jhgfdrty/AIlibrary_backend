# -*- coding: utf-8 -*-
"""
@File: insert_announcements.py
@author: Lu Yingjie
@time: April 08, 2025 10:12
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from api.models import Announcement

class Command(BaseCommand):
    help = "Insert 10 test announcements into the database"

    def handle(self, *args, **options):
        titles = [
            "Library Closure Notice",
            "New Book Recommendation Event",
            "System Maintenance Announcement",
            "Summer Opening Hours Adjustment",
            "Library Borrowing Policy Update",
            "Reading Share Session Invitation",
            "Electronic Resources Usage Guide",
            "Weekend Special Event",
            "Library Relocation Notice",
            "Spring Reading Challenge"
        ]
        contents = [
            "Due to a system upgrade, the library will be closed for one day this Friday.",
            "A new book recommendation event will be held this Saturday. You’re welcome to join us.",
            "The system will be under maintenance tonight. Please save your work in advance.",
            "During the summer break, opening hours are adjusted to 9:00 AM–5:00 PM.",
            "The new borrowing policy is now in effect. Please check the details.",
            "A reading share session on science fiction novels will be held this Sunday.",
            "How to use the library’s electronic resources? Click here for the guide.",
            "There’s a special event this weekend. Stay tuned for details.",
            "The library will relocate to a new site next month. Please take note.",
            "Join the Spring Reading Challenge and win wonderful prizes!"
        ]

        for i in range(10):
            title = titles[i]
            content = contents[i]
            is_visible = random.choice([True, False])
            published_at = now() - timedelta(days=random.randint(0, 30))
            Announcement.objects.create(
                title=title,
                content=content,
                is_visible=is_visible,
                published_at=published_at
            )

        self.stdout.write(self.style.SUCCESS("Successfully inserted 10 announcement records!"))
