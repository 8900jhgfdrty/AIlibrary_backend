from collections import defaultdict
import jwt
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
# from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from rest_framework.response import Response
from LibraryManagementSystem import settings
from api.models import Menu, Permission, Announcement, Book, Recommendation, Category, \
    Author, Rating
from api.models import Role
from api.serializers import LoginSerializer, AnnouncementSerializer, BookSerializer, BorrowRecordSerializer, \
    RecommendationSerializer, CategorySerializer, AuthorSerializer, UserSerializer, RatingSerializer
from utils.suanfa import get_user_behavior_from_db, recommendation
from utils.pagination import StandardResultsSetPagination
from utils.tree import PermissionTree
from utils.view import MineApiViewSet, MineModelViewSet
from utils.permissions import IsLibrarian, IsSystemAdmin, IsLibrarianOrSystemAdmin, IsReader, IsSelfOrAdmin, RbacPermission
from utils.decorators import role_required, librarian_required, system_admin_required, reader_required
import pandas as pd
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from .models import BorrowRecord, User
from django.http import HttpResponse
from rest_framework import status
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
import os
from django.db.models.functions import Extract
import io
import base64
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from sklearn.ensemble import IsolationForest
import pandas as pd
from django.db.models import Avg, Count
from django.db.models import Q, F, Sum
import pytz
import warnings
import numpy as np

from django.db.models import Count 

class LoginView(MineApiViewSet):
    authentication_classes = []
    permission_classes = []  # No authentication required for login interface
    @swagger_auto_schema(
        request_body=LoginSerializer,  # Request body serializer
        responses={
            200: openapi.Response(description="Successful login response",
                                  schema=openapi.Schema(type='object', properties={
                                      'token': openapi.Schema(type='string')
                                  })),
            400: openapi.Response(description="Invalid credentials response",
                                  schema=openapi.Schema(type='object', properties={
                                      'message': openapi.Schema(type='array', items=openapi.Schema(type='string'))
                                  }))
        },
        security=[],
        operation_summary="User login and get JWT Token",
        operation_description="Login with username and password, returns a JWT Token if successful"
    )
    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user_object = User.objects.filter(**ser.data).first()
        if not user_object:
            raise ValidationError({'message': ["Invalid username or password or user_type"]})
        

        user_object.last_login = timezone.now()
        user_object.save(update_fields=['last_login'])
        
        token = jwt.encode(
            payload={
                'id': user_object.id,
                'username': user_object.username,
                'exp': timezone.now() + timezone.timedelta(days=7),
                "is_super": user_object.is_super,  # Add is_super field to payload
                "user_type": user_object.user_type,
            },
            key=settings.SECRET_KEY,
            algorithm="HS256",
            headers={
                'typ': 'jwt',
                'alg': 'HS256'
            }
        )
        try:
            if user_object.is_super:
                all_permissions = Permission.objects.all()
            else:
                all_permissions = Permission.objects.filter(role__users=user_object).distinct()
        except Exception as e:
            all_permissions = Permission.objects.none()
        menu_permissions_dict = {}
        for perm in all_permissions:
            for menu in perm.menu_set.all():
                if menu.id not in menu_permissions_dict:
                    menu_permissions_dict[menu.id] = []
                menu_permissions_dict[menu.id].append({
                    'route': perm.route,
                    'method': perm.method
                })
        top_menus = Menu.objects.filter(parent_id__isnull=True).distinct()
        route_method_dict = {}
        for row in all_permissions.values('route', 'method'):
            route = row['route']
            method = row['method']
            if route not in route_method_dict:
                route_method_dict[route] = set() 
            route_method_dict[route].add(method)
        menu_tree = [PermissionTree(user_object).build_menu_tree(menu, menu_permissions_dict) for menu in top_menus]
        context = {
            "user_id": user_object.id,
            "username": user_object.username,
            "user_type": int(user_object.user_type),
            "token": token,
            "permission": route_method_dict,
            "menu": menu_tree
        }

        return Response(context)


class AnnouncementViewSet(MineModelViewSet):
    """
    Announcement ViewSet, supporting CRUD operations.
    """
    queryset = Announcement.objects.all().order_by('-published_at')
    serializer_class = AnnouncementSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    permission_classes = [RbacPermission]  # Basic permission check
    
    def get_permissions(self):
        """
        Return different permissions based on different operations
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'toggle_visibility']:
            return [IsLibrarianOrSystemAdmin()]
        return super().get_permissions()
    
    @action(detail=True, methods=['patch'], url_path='toggle-visibility')
    def toggle_visibility(self, request, pk=None):
        """
        Toggle announcement visibility status (publish/unpublish)
        """
        try:
            # Get announcement object
            announcement = self.get_object()
            
            # Toggle visibility status
            announcement.is_visible = not announcement.is_visible
            announcement.save()
            
            # Return updated status
            serializer = self.get_serializer(announcement)
            return Response({
                "message": f"Announcement has been {'published' if announcement.is_visible else 'unpublished'}",
                "is_visible": announcement.is_visible,
                "announcement": serializer.data
            })
            
        except Announcement.DoesNotExist:
            return Response(
                {"error": "Announcement does not exist"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    @librarian_required
    def create(self, request, *args, **kwargs):
        title = request.data.get('title', '').strip()
        if not title:
            return Response(
                {"title": ["Announcement title cannot be empty"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        if Announcement.objects.filter(title=title).exists():
            return Response(
                {"title": ["An announcement with this title already exists, please use a different title"]},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "code": 200,
            "success": True,
            "message": "Announcement created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def get_queryset(self):
        """
        Filter announcements based on user type
        """
        queryset = Announcement.objects.all().order_by('-published_at')
        
        # Get user info and log details
        user = self.request.user
        
        # Determine if user is admin
        is_admin = False
        
        # Method 1: Check user type (if set)
        if hasattr(user, 'user_type') and user.user_type:
            user_type_value = user.user_type
            # 1 is librarian, 2 is system admin
            if str(user_type_value) == '1' or user_type_value == 1 or str(user_type_value) == '2' or user_type_value == 2:
                is_admin = True
        
        # Method 2: Check username (backup check)
        if not is_admin and hasattr(user, 'username'):
            if user.username == 'admin' or user.username == 'librarian':
                is_admin = True
        
        # Method 3: Check user roles
        if not is_admin and hasattr(user, 'roles'):
            role_names = user.roles  # roles is already a list
            if any(role in ['Librarian', 'System Admin', 'admin', 'librarian', 'librarian', 'system_admin'] for role in role_names):
                is_admin = True
        
        # Method 4: Check if superuser
        if not is_admin and getattr(user, 'is_superuser', False):
            is_admin = True
        
        # Compatibility mode: Also check URL parameters
        if not is_admin:
            user_type_param = self.request.query_params.get('user_type', None)
            is_librarian_param = self.request.query_params.get('is_librarian', 'false').lower() == 'true'
            if user_type_param in ['1', '2'] or is_librarian_param:
                is_admin = True
        
        print(f"Is admin: {is_admin}")
        
        # Get query parameters
        title = self.request.query_params.get('title', None)
        if title:
            queryset = queryset.filter(title__icontains=title)
        
        # Only non-admins need visibility filtering
        if not is_admin:
            print("Filtering: Show only published announcements")
            queryset = queryset.filter(is_visible=True)
        else:
            print("No filtering: Show all announcements (published and unpublished)")
        
        return queryset

    @librarian_required
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @librarian_required
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @librarian_required
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

class BookViewSet(MineModelViewSet):
    """Book ViewSet"""
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        'title': ['icontains'],  
        'category': ['exact']
    }
    
    @librarian_required
    def create(self, request, *args, **kwargs):
        """
        Book creation implementation:
        1. Check if book title, author and category are not empty
        2. Check if book title already exists
        3. Process author name: find or create author record
        4. Process category name: find or create category record
        """
        data = request.data.copy()
        
        # 1. Check if title is empty
        title = data.get('title')
        if not title or not title.strip():
            return Response(
                {"title": ["Book title cannot be empty"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. Check if author is empty
        author_name = data.get('author')
        if not author_name or not str(author_name).strip():
            return Response(
                {"author": ["Author cannot be empty"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 3. Check if category is empty
        category_name = data.get('category')
        if not category_name or not str(category_name).strip():
            return Response(
                {"category": ["Category cannot be empty"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 4. Check if title already exists
        if Book.objects.filter(title=title.strip()).exists():
            return Response(
                {"title": ["Book already exists"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 5. Process author name (find or create author)
        if isinstance(author_name, str):
            author_obj, created = Author.objects.get_or_create(name=author_name.strip())
            data['author'] = author_obj.id
            
        # 6. Process category name (find or create category)
        if isinstance(category_name, str):
            category_obj, created = Category.objects.get_or_create(name=category_name.strip())
            data['category'] = category_obj.id
            
        # 7. Create book record
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            {
                "success": True,
                "message": "Book created successfully",
                "data": serializer.data
            }, 
            status=status.HTTP_201_CREATED, 
            headers=headers
        )

    @librarian_required
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @librarian_required
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @librarian_required
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        """
        Override get_queryset to handle additional filtering
        """
        queryset = super().get_queryset()
        
        # Get filter parameters
        category = self.request.query_params.get('category', None)
        title = self.request.query_params.get('title', None)
        
        # Apply filters if parameters are provided
        if category:
            queryset = queryset.filter(category_id=category)
        if title:
            queryset = queryset.filter(title__icontains=title)
            
        return queryset

class BorrowRecordViewSet(MineModelViewSet):
    """
    Borrow Record ViewSet
    """
    serializer_class = BorrowRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']
    permission_classes = [RbacPermission]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    def get_permissions(self):
        """
        Return different permissions based on different operations
        """
        if self.action in ['approve_borrow', 'pending_approvals']:
            return [IsLibrarianOrSystemAdmin()]
        elif self.action in ['create', 'return_book']:
            return [IsReader()]
        elif self.action in ['update', 'partial_update']:
            return [IsSelfOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        """
        Return different querysets based on user role:
        - Administrators can view all records
        - Regular users can only view their own records
        """
        queryset = BorrowRecord.objects.all()
        user = self.request.user
        
        # Check if user is admin using permission class
        is_admin = IsLibrarianOrSystemAdmin().has_permission(self.request, self)
        
        # Only filter by user ID if user is authenticated and not admin
        if user and user.is_authenticated and not is_admin:
            # Check if user object is not None and is authenticated
            queryset = queryset.filter(user_id=user.id)
        
        # Handle filter parameters
        book_title = self.request.query_params.get('title')
        username = self.request.query_params.get('username')
        status = self.request.query_params.get('status')
        
        if book_title:
            queryset = queryset.filter(book__title__icontains=book_title)
        if username and is_admin:  # Only admins can filter by username
            queryset = queryset.filter(user__username__icontains=username)
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset
    
    @reader_required
    def create(self, request, *args, **kwargs):
        """When creating a borrow record"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        auth_user = self.request.user
        if hasattr(auth_user, 'id') and auth_user.id is not None:
            try:
                # Find user instance in database by ID
                db_user = User.objects.get(id=auth_user.id)
                # Set initial status to pending (waiting for approval)
                record = serializer.save(user=db_user, status='pending')
            except User.DoesNotExist:
                # If user does not exist in database, only use status
                record = serializer.save(status='pending')
        else:
            # Otherwise, use user_id in request data, still set status to pending
            record = serializer.save(status='pending')
            
        headers = self.get_success_headers(serializer.data)
        
    
        return Response({
            "message": "Borrow request submitted successfully, awaiting admin approval",
            "success": True,
            "record_id": record.id,
            "book": {
                "id": record.book.id,
                "title": record.book.title
            },
            "borrower": {
                "id": record.user.id,
                "username": record.user.username,
                "type": str(record.user.user_type)
            },
            "status": {
                "code": "pending",
                "display": "Pending Approval",
                "color": "orange"
            },
            "dates": {
                "borrow": record.borrow_date,
                "return": record.return_date,
                "is_overdue": False,
                "days_remaining": None
            }
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    @reader_required
    @action(detail=True, methods=['post'], url_path='return')
    def return_book(self, request, pk=None):
        """
        User requests to return a book
        """
        try:
            borrow_record = self.get_object()
            if borrow_record.status != 'borrowed':
                return Response({"error": "Only borrowed books can be returned"}, 
                            status=status.HTTP_400_BAD_REQUEST)
            
            borrow_record.status = 'pending' 
            borrow_record.save()
            
            return Response({
                "message": "Return request submitted, awaiting admin confirmation",
                "status": "pending",
                "book_id": borrow_record.book.id,
                "book_title": borrow_record.book.title,
                "button_text": "Return Processing"
            })
            
        except BorrowRecord.DoesNotExist:
            return Response({"error": "Borrow record does not exist"}, 
                        status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve_borrow(self, request, pk=None):
        """
        Administrator approves borrow or return request
        """
        try:
            borrow_record = self.get_object()
            approval_status = request.data.get('status')
            
            if borrow_record.status == 'pending':
                if approval_status not in ['borrowed', 'rejected']:
                    return Response({"error": "Approval status must be 'borrowed'(approve) or 'rejected'(reject)", "success": False}, 
                                status=status.HTTP_400_BAD_REQUEST)
                
                borrow_record.status = approval_status
                if approval_status == 'borrowed':
                    borrow_record.return_date = timezone.now() + timezone.timedelta(days=15)
                    book = borrow_record.book
                    book.is_available = False
                    book.save()
                
                borrow_record.save()
                
                return Response({
                    "message": "Borrow request has been " + ("approved" if approval_status == 'borrowed' else "rejected"),
                    "status": approval_status,
                    "success": True,
                    "book_id": borrow_record.book.id,
                    "book_title": borrow_record.book.title,
                    "record_id": borrow_record.id,
                    "user_id": borrow_record.user.id,
                    "username": borrow_record.user.username,
                    "button_text": "Borrowed" if approval_status == 'borrowed' else "Available",
                    "action_type": "approve_borrow",
                    "refresh_needed": True,
                    "expected_return_date": borrow_record.return_date if approval_status == 'borrowed' else None
                })
                
            elif borrow_record.status == 'approval':
                borrow_record.status = 'returned'
                book = borrow_record.book
                book.is_available = True
                book.save()
                borrow_record.save()
                
                return Response({
                    "message": "Return request has been approved",
                    "status": 'returned',
                    "success": True,
                    "book_id": borrow_record.book.id,
                    "book_title": borrow_record.book.title,
                    "record_id": borrow_record.id,
                    "user_id": borrow_record.user.id,
                    "username": borrow_record.user.username,
                    "button_text": "Available",
                    "action_type": "approve_return",
                    "refresh_needed": True
                })
            
            else:
                return Response({"error": f"Cannot approve record with current status '{borrow_record.status}'", "success": False}, 
                            status=status.HTTP_400_BAD_REQUEST)
            
        except BorrowRecord.DoesNotExist:
            return Response({"error": "Borrow record does not exist", "success": False}, 
                        status=status.HTTP_404_NOT_FOUND)

    @swagger_auto_schema(
        method='get',
        manual_parameters=[
            openapi.Parameter(
                'book_id',
                openapi.IN_QUERY,
                description="Check the borrowing status of a specific book for the current user",
                type=openapi.TYPE_INTEGER,
                required=False
            )
        ],
        responses={
            200: openapi.Response('book status', BorrowRecordSerializer(many=False)),
            400: 'invalid request (missing book_id or book_id is invalid)',
            401: 'unauthorized access',
            404: 'not found (book does not exist or record does not exist)'
        },
        operation_summary="check book status",
        operation_description="check the borrowing status of a specific book for the current user"
    )
    @action(detail=False, methods=['get'], url_path='check-book-status')
    def check_book_status(self, request):
        """
        Check the borrowing status of a specific book for the current user
        """
        # Get current user and requested book ID
        user = request.user
        # Get the book ID from the query parameters
        book_id_str = request.query_params.get('book_id')

        if not book_id_str:
            return Response({"error": "Book ID must be provided"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            book_id = int(book_id_str) # Validate if it is a valid integer
        except ValueError:
            return Response({"error": "Book ID must be a valid integer"}, status=status.HTTP_400_BAD_REQUEST)

        # Status description mapping - user-friendly description text
        status_descriptions = {
            'pending': 'Your borrowing request is awaiting approval',
            'borrowed': 'You have successfully borrowed this book',
            'returned': 'You have returned this book',
            'rejected': 'Your borrowing request has been rejected',
            'approval': 'Your return request is awaiting approval'  # Add return request status description
        }

        # Button text mapping - text to display on buttons for different statuses
        button_texts = {
            'pending': 'Pending',
            'borrowed': 'Borrowed',
            'returned': 'Returned',
            'rejected': 'Rejected',
            'available': 'Available',
            'approval': 'Return Processing'  # Add return request status button text
        }

        # Check if user is authenticated
        if hasattr(user, 'id') and user.id is not None:
            latest_record = BorrowRecord.objects.filter(
                user_id=user.id,
                book_id=book_id
            ).order_by('-borrow_date').first()

            if latest_record:
                record_status = latest_record.status

                # If the latest record is "returned" or "rejected" status, consider it available for borrowing
                if record_status in ['returned', 'rejected']:
                        return Response({
                            "book_id": book_id,
                            "status": "available",
                            "status_description": "This book is currently available for borrowing",
                            "button_text": button_texts['available'],
                            "can_borrow": True
                        })

                response_data = {
                    "book_id": book_id,
                    "status": record_status,
                    "record_id": latest_record.id,
                    "borrow_date": latest_record.borrow_date,
                    "status_description": status_descriptions.get(record_status, "Unknown status"),
                    "button_text": button_texts.get(record_status, "Available"),
                    "can_borrow": record_status in ['returned', 'rejected'], # Only after returning or rejecting can it be borrowed again
                }

                # If there's a return date and status is borrowed, show return date
                if latest_record.return_date and record_status == 'borrowed':
                    response_data["return_date"] = latest_record.return_date
                    response_data["expected_return_date"] = latest_record.return_date
                    # Calculate days remaining
                    today = timezone.now().date()
                    return_date = latest_record.return_date.date()
                    days_remaining = (return_date - today).days
                    response_data["days_remaining"] = days_remaining
                    response_data["return_date_info"] = f"Should be returned on {return_date.strftime('%Y-%m-%d')}"

                return Response(response_data)

        # If no record found for the user, check if the book exists and is generally available
        try:
             book = Book.objects.get(id=book_id) # Check if book exists
        except Book.DoesNotExist:
             return Response({"error": f"Book with ID {book_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        # Book exists, user has no record, so it's available for this user
        return Response({
            "book_id": book_id,
            "status": "available",
            "status_description": "This book is currently available for borrowing",
            "button_text": button_texts['available'],
            "can_borrow": True
        })
    
    @swagger_auto_schema(auto_schema=None)  # Hide this endpoint from Swagger documentation
    @action(detail=False, methods=['get'], url_path='pending-approvals')
    def pending_approvals(self, request):
        """
        Get all pending borrow requests
        """
        pending_records = BorrowRecord.objects.filter(status='pending').order_by('-borrow_date')
        
        page = self.paginate_queryset(pending_records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            data = serializer.data
            for record in data:
                record['has_approve_buttons'] = True
                record['approve_url'] = f"/api/borrow-records/{record['id']}/approve/"
                record['can_approve'] = True
            
            paginated_response = self.get_paginated_response(data)
            paginated_response.data['is_approval_list'] = True
            return paginated_response
        
        serializer = self.get_serializer(pending_records, many=True)
        data = serializer.data
        for record in data:
            record['has_approve_buttons'] = True
            record['approve_url'] = f"/api/borrow-records/{record['id']}/approve/"
            record['can_approve'] = True
        
        return Response({
            "results": data,
            "is_approval_list": True,
            "count": len(data)
        })

class RecommendationViewSet(MineModelViewSet):
    """recommendation view set
    """
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer
    http_method_names = ['get', 'head', 'options']
    
    def get_queryset(self):
        """only normal users can view their own recommendation results
        """
        # 检查是否在swagger生成schema时被调用
        if getattr(self, 'swagger_fake_view', False):
            # 返回空查询集，避免实际查询数据库
            return Recommendation.objects.none()
            
        user = self.request.user
        # 添加用户检查以避免NoneType错误
        if user and hasattr(user, 'id'):
            return Recommendation.objects.filter(user_id=user.id)
        return Recommendation.objects.none()
    
    @system_admin_required
    @action(detail=False, methods=['get'], url_path="popular_books_analysis")
    def popular_books_analysis(self, request):
        """
        Popular category analysis API: Analyze which book categories are most popular, with optional AI summary
        :param request: Contains top_n parameter and add_ai_summary parameter
        :return: JSON data containing format suitable for BI chart display
        """
        # Get parameters
        top_n = int(self.request.GET.get('top_n', 5))  # Default show top 5 popular categories
        add_ai_summary = self.request.GET.get('add_ai_summary', 'false').lower() == 'true'  # Whether to add AI summary
        
        # Count borrowings by category
        category_stats = (
            BorrowRecord.objects.filter(status='borrowed')
            .values('book__category__id', 'book__category__name')
            .annotate(borrow_count=Count('id'))
            .order_by('-borrow_count')
        )
        
        # Handle possibly empty categories
        categories = []
        for stat in category_stats:
            category_name = stat['book__category__name'] or "Uncategorized"
            categories.append({
                "category_id": stat['book__category__id'],
                "category_name": category_name,
                "borrow_count": stat['borrow_count'],
                "percentage": 0  # Initialize as 0, calculate later
            })
        
        # Calculate total borrowings
        total_borrows = sum(cat['borrow_count'] for cat in categories)
        
        # Calculate percentage for each category
        if total_borrows > 0:
            for category in categories:
                category['percentage'] = round((category['borrow_count'] / total_borrows) * 100, 2)
        
        # Keep only top_n categories
        top_categories = categories[:top_n]
        
        # Get popular books in each category
        for category in top_categories:
            category_name = category['category_name']
            
            # Query popular books in this category
            top_books_in_category = (
                BorrowRecord.objects.filter(
                    status='borrowed',
                    book__category__name=category_name if category_name != "Uncategorized" else None
                )
                .values('book__id', 'book__title')
                .annotate(borrow_count=Count('id'))
                .order_by('-borrow_count')[:3]  # Get top 3 popular books in each category
            )
            
            # Add to category data
            category['top_books'] = [
                {
                    "book_id": book['book__id'],
                    "book_title": book['book__title'],
                    "borrow_count": book['borrow_count']
                }
                for book in top_books_in_category
            ]
        
        ai_summary = None
        if add_ai_summary and categories:
            most_popular = categories[0]['category_name']
            total_categories = len(categories)
            top_three = [cat['category_name'] for cat in categories[:3]] if len(categories) >= 3 else [cat['category_name'] for cat in categories]
            
            # Build summary text (fix Chinese quote issue)
            summary_text = f"According to analysis, among all {total_categories} book categories, \"{most_popular}\" is the most popular, accounting for {categories[0]['percentage']}% of total borrowings."
            
            if len(top_three) >= 3:
                summary_text += f" The top three popular categories are: {top_three[0]}, {top_three[1]} and {top_three[2]}, "
                total_percentage = sum(cat['percentage'] for cat in categories[:3])
                summary_text += f"together accounting for {round(total_percentage, 2)}% of total borrowings."
            
            # Analyze trends and reader interests
            if categories[0]['percentage'] > 40:
                summary_text += f" Readers show a clear preference for \"{most_popular}\" books, suggesting the library should increase acquisitions in this category."
            elif total_categories > 5 and categories[4]['percentage'] > 10:
                summary_text += " Reader interests are quite diverse, with all top five categories having significant borrowing numbers. The library should maintain a balanced distribution of book categories."
            
            ai_summary = {
                "text": summary_text,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_based_on": f"Analysis based on {total_borrows} borrowing records"
            }
        
        # Prepare data format suitable for BI charts
        chart_data = {
            "pie_chart": {
                "title": "Book Category Borrowing Distribution",
                "series": [{
                    "name": "Borrowing Count",
                    "data": [{"name": cat["category_name"], "value": cat["borrow_count"]} for cat in top_categories]
                }]
            },
            "bar_chart": {
                "title": "Popular Book Categories Analysis",
                "xAxis": {"data": [cat["category_name"] for cat in top_categories]},
                "series": [{
                    "name": "Borrowing Count",
                    "type": "bar",
                    "data": [cat["borrow_count"] for cat in top_categories]
                }]
            },
            "percentage_chart": {
                "title": "Borrowing Percentage Distribution",
                "series": [{
                    "name": "Percentage",
                    "data": [{"name": cat["category_name"], "value": cat["percentage"]} for cat in top_categories]
                }]
            }
        }
        
        # Return JSON data
        response_data = {
            "top_categories": top_categories,
            "total_borrows": total_borrows,
            "categories_count": len(categories),
            "chart_data": chart_data
        }
        
        # If requested AI summary, add to response
        if ai_summary:
            response_data["ai_summary"] = ai_summary
        
        return Response(response_data)
    @system_admin_required
    @action(detail=False, methods=['get'], url_path="predictive_analysis")
    def predictive_analysis(self, request):
        """
        Predictive analysis API - Using ARIMA model to predict future borrowing volume
        :param request: Contains future_days parameter
        :return: JSON data containing format suitable for BI chart display
        """
        future_days = int(self.request.GET.get('future_days', 30))  # Default predict next 30 days
        
        try:
            records = BorrowRecord.objects.filter(status='borrowed').values_list('borrow_date', flat=True)
            
            if not records:
                return Response({'error': 'Not enough historical borrowing data for prediction'}, status=400)
                
            dates = [record.date() for record in records]
            unique_dates = sorted(set(dates))
            date_counts = {date: dates.count(date) for date in unique_dates}
            
            date_range = pd.date_range(start=min(unique_dates), end=max(unique_dates))
            ts_data = [date_counts.get(date.date(), 0) for date in date_range]
            
            ts = pd.Series(ts_data, index=date_range)
            
            # Use fixed parameters (5, 1, 0)
            # p=5: Auto-regression order, considers influence of previous 5 time points
            # d=1: Differencing order, performs first-order differencing to make data stationary
            # q=0: Moving average order, doesn't consider random error terms
            
            # Based on analysis of book borrowing data characteristics, this parameter combination effectively captures:
            # 1. Short-term borrowing trends (through high-order auto-regression terms)
            # 2. Eliminates non-stationarity in time series (through first-order differencing)
            # 3. Balances computational efficiency and prediction accuracy
            p, d, q = 5, 1, 0
            
            model = ARIMA(ts, order=(p, d, q))
            model_fit = model.fit()
            
            forecast = model_fit.forecast(steps=future_days)
            predicted_counts = forecast.tolist()
            
            predicted_counts = [max(0, round(count)) for count in predicted_counts]
            
            last_date = max(unique_dates)
            future_dates = [(last_date + timedelta(days=i+1)).strftime('%Y-%m-%d') for i in range(future_days)]
            
            historical_dates = [date.strftime('%Y-%m-%d') for date in date_range]
            historical_counts = ts_data
            
            chart_data = {
                "time_series": {
                    "title": "Prediction of Future Book Borrowing Volume in the Library",
                    "xAxis": {
                        "type": "category",
                        "data": historical_dates + future_dates,
                        "axisLabel": {
                            "rotate": 45
                        }
                    },
                    "series": [
                        {
                            "name": "Predicted Borrowing Volume",
                            "type": "line",
                            "data": [None] * len(historical_counts) + predicted_counts,
                            "itemStyle": {"color": "#ff4d4f"},
                            "lineStyle": {"type": "dashed"}
                        }
                    ],
                    "legend": {
                        "data": ["Predicted Borrowing Volume"]
                    }
                },
                "forecast_bar": {
                    "title": "Prediction of Future Book Borrowing Volume in the Library",
                    "xAxis": {
                        "type": "category",
                        "data": future_dates,
                        "axisLabel": {
                            "rotate": 45
                        }
                    },
                    "series": [
                        {
                            "name": "Predict the borrowing volume",
                            "type": "bar",
                            "data": predicted_counts
                        }
                    ]
                }
            }
            
            return Response({
                'predicted_counts': predicted_counts,
                'future_dates': future_dates,
                'model_info': {
                    'type': 'ARIMA',
                    'parameters': f'({p},{d},{q})',
                    'data_points_used': len(ts_data)
                },
                'chart_data': chart_data
            })
            
        except Exception as e:
            return Response({
                'error': f'Error during prediction: {str(e)}',
                'suggestion': 'More data points may be needed for reliable ARIMA prediction'
            }, status=500)



class CategoryViewSet(MineModelViewSet):
    """Book Category ViewSet
    """
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    pagination_class = StandardResultsSetPagination
    
    def dispatch(self, request, *args, **kwargs):
        try:
            if 'pk' in kwargs and not kwargs['pk']:
                return Response({
                    'success': False,
                    'message': 'Category ID cannot be empty',
                    'errors': {'id': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
                
            if 'pk' in kwargs:
                try:
                    int(kwargs['pk'])
                except (ValueError, TypeError):
                    return Response({
                        'success': False,
                        'message': 'Invalid category ID format',
                        'errors': {'id': ['Must be an integer']}
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response({
                    'success': False,
                    'message': str(e.detail) if hasattr(e.detail, '__str__') else "Request parameter error",
                    'errors': e.detail
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'message': f"Request processing failed: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise ValidationError({
                'id': [f"Category with ID {self.kwargs.get('pk')} does not exist"]
            })
            
    @librarian_required
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @librarian_required
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @librarian_required
    def partial_update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            
            if 'name' not in request.data or not request.data['name']:
                return Response({
                    'success': False,
                    'message': 'Required field is not provided',
                    'errors': {'name': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
                
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            
            return Response({
                'success': True,
                'message': 'Category updated successfully',
                'data': serializer.data
            })
            
        except Http404:
            return Response({
                'success': False,
                'message': 'Category does not exist'
            }, status=status.HTTP_404_NOT_FOUND)
        except ValidationError as e:
            return Response({
                'success': False,
                'message': 'Category update failed',
                'errors': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Category update failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @librarian_required
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class AuthorViewSet(MineModelViewSet):
    """Author Information ViewSet
    Get authors
    """
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    pagination_class = StandardResultsSetPagination
    
    def dispatch(self, request, *args, **kwargs):
        try:
            if 'pk' in kwargs and not kwargs['pk']:
                return Response({
                    'success': False,
                    'message': 'Author ID cannot be empty',
                    'errors': {'id': ['This field is required']}
                }, status=status.HTTP_400_BAD_REQUEST)
                
            if 'pk' in kwargs:
                try:
                    int(kwargs['pk'])
                except (ValueError, TypeError):
                    return Response({
                        'success': False,
                        'message': 'Invalid author ID format',
                        'errors': {'id': ['Must be an integer']}
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            return super().dispatch(request, *args, **kwargs)
        except Exception as e:
            if hasattr(e, 'detail'):
                return Response({
                    'success': False,
                    'message': str(e.detail) if hasattr(e.detail, '__str__') else "Request parameter error",
                    'errors': e.detail
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'message': f"Request processing failed: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise ValidationError({
                'id': [f"Author with ID {self.kwargs.get('pk')} does not exist"]
            })
    
    @librarian_required
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @librarian_required
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @librarian_required
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @librarian_required
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class UserViewSet(MineModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['username']
    
    @action(detail=False, methods=['GET'], url_path='user-types')
    def get_user_types(self, request):
        """
        Get all available user types for frontend user creation selection
        """
        user_types = [{'value': key, 'label': value} for key, value in User.user_type.field.choices]
        return Response(user_types)
    
    def create(self, request, *args, **kwargs):
        """
        Create user and assign roles and permissions according to user type
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_type = user.user_type
        role_name_map = {
            '0': 'Reader',
            0: 'Reader',
            '1': 'Librarian',
            1: 'Librarian',
            '2': 'System Administrator',
            2: 'System Administrator'
        }
        role_name = role_name_map.get(user_type)
        if role_name:
            try:
                role = Role.objects.filter(name=role_name).first()
                if role:
                    user.roles.add(role)
                else:
                    print(f"Warning: Role named '{role_name}' not found")
            except Exception as e:
                print(f"Error: Error occurred while updating role - {str(e)}")
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    @system_admin_required
    def update(self, request, *args, **kwargs):
        """
        Update user and update corresponding roles and permissions according to user type
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # Save updated user data
        user = serializer.save()
        
        # Check if user type is updated
        if 'user_type' in request.data:
            # Get user type
            user_type = user.user_type
            
            # Assign roles according to user type
            role_name_map = {
                '0': 'Reader',        # Reader role
                0: 'Reader',          # Reader role
                '1': 'Librarian',    # Librarian role
                1: 'Librarian',      # Librarian role
                '2': 'System Administrator',    # System Administrator role
                2: 'System Administrator'       # System Administrator role
            }
            
            # Get corresponding role name
            role_name = role_name_map.get(user_type)
            
            if role_name:
                try:
                    # Remove existing roles
                    user.roles.clear()
                    
                    # Find corresponding role
                    role = Role.objects.filter(name=role_name).first()
                    if role:
                        # Assign role to user
                        user.roles.add(role)
                    else:
                        # If role doesn't exist, consider auto-creating the role
                        print(f"Warning: Role named '{role_name}' not found")
                except Exception as e:
                    print(f"Error: Error occurred while updating role - {str(e)}")
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
            
        return Response(serializer.data)

    @system_admin_required
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)
    
    @system_admin_required
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

class RatingViewSet(MineModelViewSet):
    """Book Rating and Smart Recommendation ViewSet"""
    serializer_class = RatingSerializer
    queryset = Rating.objects.all()
    # Limit the allowed HTTP methods
    http_method_names = ['get', 'post', 'head', 'options']
    
    def get_allowed_methods(self):
        allowed_methods = super().get_allowed_methods()
        if 'POST' not in allowed_methods:
            allowed_methods.append('POST')
        return allowed_methods
        
    @swagger_auto_schema(
        method='get',
        manual_parameters=[
            openapi.Parameter(
                'book_id',
                openapi.IN_QUERY,
                description="ID of the book to get user's rating for",
                type=openapi.TYPE_INTEGER,
                required=True
            )
        ],
        responses={
            200: openapi.Response('User rating information', 
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'success': openapi.Schema(type=openapi.TYPE_BOOLEAN),
                        'message': openapi.Schema(type=openapi.TYPE_STRING),
                        'data': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'score': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'comment': openapi.Schema(type=openapi.TYPE_STRING),
                                'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                            }
                        )
                    }
                )
            ),
            400: 'Bad Request - Book ID is missing',
            401: 'Unauthorized - User not logged in'
        }
    )
    @reader_required
    @action(detail=False, methods=['GET'])
    def get_user_rating(self, request):
        try:
            if getattr(self, 'swagger_fake_view', False):
                return Response({
                    'success': True,
                    'message': 'Swagger schema generation',
                    'data': None
                })
                
            book_id = request.query_params.get('book_id')
            if not book_id:
                return Response({
                    'success': False,
                    'message': 'Book ID cannot be empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            try:
                book = Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Book not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            user = request.user
            try:
                rating = Rating.objects.get(user_id=user.id, book_id=book_id)
                return Response({
                    'success': True,
                    'message': 'Successfully retrieved rating',
                    'data': {
                        'score': rating.score,
                        'comment': rating.comment,
                        'created_at': rating.created_at
                    }
                })
            except Rating.DoesNotExist:
                return Response({
                    'success': True,
                    'message': 'User has not rated yet',
                    'data': None
                })
                
        except Exception as e:
            return Response({
                'success': False,
                'message': f'Failed to get rating: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @reader_required
    def create(self, request, *args, **kwargs):
        """Create book rating - only allowed for readers"""
        try:
            user = request.user
            data = request.data.copy()
            data['user'] = user.id
            
            # Check if book exists
            book_id = data.get('book')
            if not book_id:
                return Response({
                    'success': False,
                    'message': 'Book ID cannot be empty'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Check if score is an integer
            if 'score' in data:
                try:
                    score = int(data['score'])
                    data['score'] = score
                except (ValueError, TypeError):
                    return Response({
                        'success': False,
                        'message': 'Score must be an integer'
                    }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    'success': False,
                    'message': 'Score cannot be empty'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if book exists in database
            try:
                Book.objects.get(id=book_id)
            except Book.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Book does not exist'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Use serializer to validate and create rating
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            return Response({
                'success': True,
                'message': 'Rating submitted successfully',
                'data': serializer.data
            }, status=status.HTTP_201_CREATED, headers=headers)
            
        except ValidationError as e:
            errors = e.detail
            # Check if it is an error that the book has already been rated
            if isinstance(errors, dict) and 'message' in errors and errors.get('message') == 'You have already rated this book':
                return Response({
                    'success': False,
                    'message': 'You have already rated this book',
                    'data': errors.get('data', {})
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle rating range error
            if 'score' in errors:
                return Response({
                    'success': False,
                    'message': 'Score must be between 1-5' if '1-5' in str(errors['score'][0]) else 'Score must be an integer'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Other validation errors
            return Response({
                'success': False,
                'message': 'Rating submission failed',
                'errors': errors
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Other exceptions
            return Response({
                'success': False,
                'message': f'Rating creation failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @reader_required
    @action(detail=False, methods=['GET'])
    def recommended_books(self, request):
        # Check if it is called when generating swagger schema
        if getattr(self, 'swagger_fake_view', False):
            return Response({
                'success': True,
                'message': 'Swagger schema generation',
                'data': {
                    'books': [],
                    'total': 0,
                    'is_personalized': False
                }
            }, status=status.HTTP_200_OK)
            
        user = request.user
        # Add user check
        if not user or not hasattr(user, 'id'):
            return Response({
                'success': False,
                'message': 'User not authenticated',
                'data': None
            }, status=status.HTTP_401_UNAUTHORIZED)
            
        books_queryset = Book.objects.select_related('author', 'category').all()
        total_book_list = [
            {
                'id': book.id,
                'title': book.title,
                'author_name': book.author.name,
                'category_name': book.category.name,
                'description': book.description
            } for book in books_queryset
        ]
        recommended_books = recommendation(
            total_book_list,
            user.username
        )
        if not recommended_books:
            latest_books = Book.objects.select_related('author', 'category').order_by('-id')[:10]
            recommended_books = [
                {
                    'id': book.id,
                    'title': book.title,
                    'author_name': book.author.name,
                    'category_name': book.category.name,
                    'description': book.description,
                    'recommendation_type': 'latest'
                } for book in latest_books
            ]
            is_personalized = False
        else:
            recommended_books = recommended_books[:10]
            for book in recommended_books:
                book['recommendation_type'] = 'smart'
            is_personalized = True

        return Response({
            'success': True,
            'message': 'Get recommended books successfully',
            'data': {
                'books': recommended_books,
                'total': len(recommended_books),
                'is_personalized': is_personalized
            }
        }, status=status.HTTP_200_OK)

class RegisterView(MineApiViewSet):
    """User registration view"""
    authentication_classes = []  # No authentication required
    permission_classes = []      # No permission required

    @swagger_auto_schema(
        request_body=UserSerializer,
        responses={
            201: "Registration successful",
            400: "Registration failed, please check the input"
        },
    )
    def post(self, request):
        """User registration"""
        # Restrict only registering reader accounts
        user_type = request.data.get('user_type')
        if user_type is not None and int(user_type) != 0:
            return Response({
                "success": False,
                "message": "Registration failed",
                "errors": {
                    "user_type": ["Only reader accounts can be registered"]
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if username already exists
        username = request.data.get('username')
        if username and User.objects.filter(username=username).exists():
            return Response({
                "success": False,
                "message": "Registration failed",
                "errors": {
                    "username": ["This username already exists, please use another username"]
                }
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Create a copy of the request data to ensure user_type is set to 0
        data = request.data.copy()
        data['user_type'] = 0  # Force set to reader type
        
        serializer = UserSerializer(data=data)
        
        if serializer.is_valid():
            # Set user role to reader and ensure account activation
            user = serializer.save(user_type=0, is_active=True)  # 0 represents reader
            
            # Assign reader role
            try:
                reader_role = Role.objects.get(name='Reader')
                user.roles.add(reader_role)
            except Role.DoesNotExist:
                print("Warning: 'Reader' role does not exist")
                # Do not return an error if the role does not exist, just do not assign the role
            
            return Response({
                "success": True,
                "message": "Registration successful",
                "data": {
                    "user_id": user.id,
                    "username": user.username
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            "success": False,
            "message": "Registration failed",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
