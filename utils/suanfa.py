from collections import defaultdict
import os
import sys
import django
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'LibraryManagementSystem.settings')
django.setup()
from api.models import Rating, User, Book
def get_user_behavior_from_db():
    user_behavior = defaultdict(dict)
    ratings = Rating.objects.select_related('user', 'book').all()
    for rating in ratings:
        username = rating.user.username
        book_id = rating.book.id
        score = rating.score
        user_behavior[username][book_id] = score
    return user_behavior
def calculate_user_similarity(user_behavior):
    users = list(user_behavior.keys())
    n_users = len(users)
    all_books = sorted({bid for ratings in user_behavior.values() for bid in ratings})
    user_ratings_matrix = np.zeros((n_users, len(all_books)))
    for i, user in enumerate(users):
        for j, book_id in enumerate(all_books):
            user_ratings_matrix[i, j] = user_behavior[user].get(book_id, 0)
    similarity_matrix = cosine_similarity(user_ratings_matrix)
    return users, similarity_matrix
def collaborative_filter(user_behavior, target_user, candidate_books):
    if not user_behavior or target_user not in user_behavior:
        return []    
    users, similarity_matrix = calculate_user_similarity(user_behavior)
    target_idx = users.index(target_user)
    predicted_scores = {}
    for book in candidate_books:
        bid = book['id']
        if bid in user_behavior[target_user]:
            continue
        weighted_sum = 0.0
        sim_sum = 0.0
        for i, user in enumerate(users):
            if user == target_user or bid not in user_behavior[user]:
                continue
            sim = similarity_matrix[target_idx, i]
            weighted_sum += sim * user_behavior[user][bid]
            sim_sum += sim
        if sim_sum > 0:
            predicted_scores[bid] = weighted_sum / sim_sum
    return sorted(candidate_books, key=lambda b: predicted_scores.get(b['id'], 0), reverse=True)
def recommendation(books, username):
    user_behavior = get_user_behavior_from_db()
    if not user_behavior or not username:
        return []
    return collaborative_filter(user_behavior, username, books)
