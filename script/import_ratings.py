# -*- coding: utf-8 -*-
"""
Rating data import script
Batch import user rating data into the database for the intelligent recommendation system
"""
import os
import sys
import django
import random
from datetime import datetime, timedelta

# 将项目根目录添加到Python路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()

from django.utils.timezone import make_aware
from api.models import User, Book, Rating

# User rating data
user_ratings = {
    # Admin users
    "admin": {1: 5, 3: 4, 5: 5, 7: 3, 9: 4},  # Prefers literature and history
    "root": {2: 4, 4: 5, 6: 3, 8: 4, 10: 5},  # Prefers technology and literature
    
    # Reader users
    "reader": {1: 3, 2: 4, 5: 5, 8: 4, 9: 5},  # Literature enthusiast
    "luna": {3: 5, 6: 4, 7: 5, 10: 3},        # History enthusiast
    "jerry": {2: 5, 4: 4, 6: 3, 10: 5},        # Technology enthusiast
    "alex": {1: 4, 3: 5, 5: 3, 7: 4, 9: 5},    # Literature enthusiast
    "emma": {2: 3, 4: 4, 8: 5, 10: 4},         # Mixed interests
    "oliver": {1: 5, 3: 4, 5: 5, 9: 3},        # Literature enthusiast
    "sophia": {6: 4, 7: 5, 10: 3},             # History and technology enthusiast
    "ethan": {2: 5, 6: 3, 10: 5},              # Technology enthusiast
    "mia": {1: 4, 5: 5, 8: 4, 9: 5},           # Literature enthusiast
    "noah": {3: 3, 6: 4, 7: 5},                # History enthusiast
    "lily": {1: 5, 3: 4, 5: 5, 8: 3, 9: 4},    # Literature enthusiast
    "william": {2: 4, 4: 3, 10: 5},            # Technology enthusiast
    "ava": {3: 5, 6: 4, 7: 5},                 # History enthusiast
    "james": {1: 3, 5: 4, 8: 5, 9: 4},         # Literature enthusiast
    "grace": {2: 5, 10: 4},                    # Technology enthusiast
    "logan": {3: 4, 6: 5, 7: 3},               # History enthusiast
    "zoe": {1: 5, 5: 4, 8: 3, 9: 5},           # Literature enthusiast
    "benjamin": {2: 3, 4: 4, 10: 5},           # Technology enthusiast
    "chloe": {1: 4, 5: 5, 9: 3},               # Literature enthusiast
    "lucas": {6: 4, 7: 5, 10: 3},              # History and technology enthusiast
    "user1": {1: 4, 3: 5, 5: 4, 7: 3, 9: 5}    # Similar preferences to target_user
}

# Comment templates for random generation
comment_templates = [
    "This book is very {adj}, {detail}.",
    "As a {category} book, it {detail}.",
    "A {adj} book, {detail}.",
    "After reading, I feel {detail}, a {adj} experience.",
    "The {aspect} of this book is {adj}, {detail}.",
    "{adj}! {detail}.",
    "This book {detail}, overall feeling {adj}.",
    "The {aspect} is very {adj}, {detail}.",
]

# Rating adjectives
adjectives = {
    1: ["terrible", "boring", "disappointing", "waste of time", "not worth reading"],
    2: ["mediocre", "plain", "not engaging", "somewhat dull", "barely readable"],
    3: ["okay", "standard", "acceptable", "worth a read", "satisfactory"],
    4: ["good", "engaging", "recommended", "very good", "interesting"],
    5: ["excellent", "outstanding", "fantastic", "amazing", "must-read"]
}

# Book categories
book_categories = {
    1: "Literature", 2: "Literature", 3: "History", 4: "Literature", 5: "Literature",
    6: "History", 7: "History", 8: "Literature", 9: "Literature", 10: "Technology"
}

# Rating details
details = {
    1: ["content too monotonous", "story plot inconsistent", "writing style stiff", "failed to interest me", "lacks depth"],
    2: ["some parts not well written", "plot develops slowly", "some chapters have highlights", "creative but mediocre execution", "not engaging enough"],
    3: ["content fairly rich", "reading experience acceptable", "meets expectations", "some chapters are great", "plot is okay"],
    4: ["plot development tight", "vivid character portrayal", "beautiful and flowing language", "thought-provoking", "many brilliant passages"],
    5: ["profoundly changed my way of thinking", "couldn't put it down", "engaging until the last page", "unique narrative style", "brilliantly conceived"]
}

# Book aspects
aspects = ["plot", "character development", "writing style", "theme", "structure", "creativity", "depth of thought", "narrative technique"]

def generate_comment(score, book_id):
    """Generate a random comment based on rating"""
    category = book_categories.get(book_id, "general")
    adj = random.choice(adjectives[score])
    detail = random.choice(details[score])
    aspect = random.choice(aspects)
    template = random.choice(comment_templates)
    
    return template.format(adj=adj, detail=detail, category=category, aspect=aspect)

def import_ratings():
    """Import rating data into database"""
    print("Starting to import rating data...")
    
    # Clear existing rating data
    Rating.objects.all().delete()
    print("Cleared existing rating data")
    
    # Bulk create ratings
    ratings_to_create = []
    success_count = 0
    error_count = 0
    
    for username, ratings in user_ratings.items():
        try:
            # Get user
            user = User.objects.get(username=username)
            
            for book_id, score in ratings.items():
                try:
                    # Get book
                    book = Book.objects.get(id=book_id)
                    
                    # Generate comment
                    comment = generate_comment(score, book_id)
                    
                    # Create time randomly within past 30 days
                    days_ago = random.randint(0, 30)
                    created_at = make_aware(datetime.now() - timedelta(days=days_ago))
                    
                    # Create rating object
                    ratings_to_create.append(
                        Rating(
                            user=user,
                            book=book,
                            score=score,
                            comment=comment,
                            created_at=created_at
                        )
                    )
                    success_count += 1
                except Book.DoesNotExist:
                    print(f"Error: Book ID {book_id} does not exist")
                    error_count += 1
                    continue
        except User.DoesNotExist:
            print(f"Error: User {username} does not exist")
            error_count += 1
            continue
    
    # Bulk create
    if ratings_to_create:
        Rating.objects.bulk_create(ratings_to_create)
        print(f"Successfully imported {success_count} rating records")
    
    if error_count > 0:
        print(f"There were {error_count} errors during import")
    
    print("Rating data import completed")

if __name__ == "__main__":
    import_ratings() 