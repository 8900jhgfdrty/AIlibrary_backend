# -*- coding: utf-8 -*-
"""
@File: urls.py.py
@author: Lu Yingjie
@time: 4月 09, 2025 9:39
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api import views
from api.views import LoginView, AnnouncementViewSet, BookViewSet, BorrowRecordViewSet, \
    RecommendationViewSet, RegisterView, CategoryViewSet, AuthorViewSet, UserViewSet, RatingViewSet

router = DefaultRouter()
router.register(r'announcements', AnnouncementViewSet, basename='announcement')
router.register(r'books', BookViewSet, basename='book')
router.register(r'borrow-records', BorrowRecordViewSet, basename='borrow-record')
router.register(r'ratings', RatingViewSet)
router.register(r'recommendations', RecommendationViewSet, basename='recommendation')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'authors', AuthorViewSet, basename='author')
router.register(r'user', UserViewSet, basename='user')
urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('', include(router.urls)),
    # path('borrow-trends/', views.borrow_trends_analysis, name='borrow_trends'),
    # path('popular-books/', views.popular_books_analysis, name='popular_books'),
    # path('reader-behavior/', views.reader_behavior_analysis, name='reader_behavior'),
    # path('predictive-analysis/', views.predictive_analysis, name='predictive_analysis'),
]