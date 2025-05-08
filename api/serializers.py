# -*- coding: utf-8 -*-
"""
@File: serializers.py
@author: Lu Yingjie
@time: April 09, 2025 9:44
Convert data objects to JSON format
"""
from rest_framework import serializers
from api.models import Announcement, Book, BorrowRecord, Recommendation, Rating, Category, Author, User
from rest_framework.validators import UniqueTogetherValidator


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=32)
    password = serializers.CharField(max_length=64)
    user_type = serializers.ChoiceField(
        choices=[
            ('0', 'Reader'),
            ('1', 'Librarian'),
            ('2', 'SysAdmin'),
        ]
    )
class RatingSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(min_value=1, max_value=5, error_messages={
        'min_value': 'Rating must be between 1 and 5',
        'max_value': 'Rating must be between 1 and 5',
        'invalid': 'Rating must be an integer'
    })
    
    class Meta:
        model = Rating
        fields = ['id', 'user', 'book', 'score', 'comment', 'created_at']
        validators = [
            UniqueTogetherValidator(
                queryset=Rating.objects.all(),
                fields=['user', 'book'],
                message='You have already rated this book'
            )
        ]
        
    def validate(self, attrs):
        """Custom validation logic"""
        user = attrs.get('user')
        book = attrs.get('book')
        
        # Check if the user has already rated the book
        if Rating.objects.filter(user=user, book=book).exists():
            existing_rating = Rating.objects.get(user=user, book=book)
            raise serializers.ValidationError({
                'message': 'You have already rated this book',
                'data': {
                    'book_id': book.id,
                    'previous_score': existing_rating.score,
                    'previous_comment': existing_rating.comment,
                    'rated_at': existing_rating.created_at
                }
            })
        
        return attrs



class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = '__all__'


class BookSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Book
        fields = '__all__'


class BorrowRecordSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    borrower = serializers.CharField(source='user.username', read_only=True)
    borrower_id = serializers.IntegerField(source='user.id', read_only=True)
    borrower_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    borrower_type = serializers.CharField(source='user.user_type', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    can_approve = serializers.SerializerMethodField()
    can_return = serializers.SerializerMethodField()
    status_text = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    formatted_return_date = serializers.SerializerMethodField()
    formatted_borrow_date = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = BorrowRecord
        fields = '__all__'

    def get_can_approve(self, obj):
        """
        Determine if the record can be approved
        """
        return obj.status == 'pending'

    def get_can_return(self, obj):
        """
        Determine if the record can be returned
        """
        return obj.status == 'borrowed'

    def get_status_text(self, obj):
        """
        Get user-friendly status text
        """
        status_texts = {
            'pending': 'Pending Approval',
            'borrowed': 'Borrowed',
            'returned': 'Returned',
            'rejected': 'Rejected',
            'approval': 'Return Pending'
        }
        return status_texts.get(obj.status, obj.get_status_display())

    def get_status_color(self, obj):
        """
        Get status color code for frontend display
        """
        status_colors = {
            'pending': 'orange',  # waiting approval
            'borrowed': 'green',  # borrowed
            'returned': 'blue',   # returned
            'rejected': 'red',    # rejected
            'approval': 'purple'  # return pending
        }
        return status_colors.get(obj.status, 'default')

    def get_formatted_return_date(self, obj):
        """
        Get formatted return date
        """
        if obj.return_date:
            return obj.return_date.strftime('%Y-%m-%d')
        return None

    def get_formatted_borrow_date(self, obj):
        """
        Get formatted borrow date
        """
        if obj.borrow_date:
            return obj.borrow_date.strftime('%Y-%m-%d %H:%M:%S')
        return None
        
    def get_is_overdue(self, obj):
        """
        Check if the book is overdue
        """
        if obj.status == 'borrowed' and obj.return_date:
            from django.utils import timezone
            today = timezone.now().date()
            return_date = obj.return_date.date()
            return today > return_date
        return False
        
    def get_days_remaining(self, obj):
        """
        Calculate days remaining until return date
        """
        if obj.status == 'borrowed' and obj.return_date:
            from django.utils import timezone
            today = timezone.now().date()
            return_date = obj.return_date.date()
            return (return_date - today).days
        return None


# Return these data to the frontend
class RecommendationSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source='book.title', read_only=True)
    category_name = serializers.CharField(source='book.category.name', read_only=True)

    class Meta:
        model = Recommendation
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    """Book category serializer"""
    class Meta:
        model = Category
        fields = '__all__'


class AuthorSerializer(serializers.ModelSerializer):
    """Author info serializer"""
    class Meta:
        model = Author
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    """User info serializer"""
    formatted_last_login = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = User
        fields = '__all__'
        
    def get_formatted_last_login(self, obj):
        """Return formatted last login time"""
        if obj.last_login:
            return obj.last_login.strftime('%Y-%m-%d %H:%M:%S')
        return None
