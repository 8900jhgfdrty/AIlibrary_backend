from collections import defaultdict
import jwt
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from rest_framework.response import Response
from LibraryManagementSystem import settings
from api.models import Menu, Permission, Announcement, Book, Recommendation, Category, \
    Author
from api.models import Role
from api.serializers import LoginSerializer, AnnouncementSerializer, BookSerializer, BorrowRecordSerializer, \
    RecommendationSerializer, CategorySerializer, AuthorSerializer, UserSerializer
from utils.suanfa import user_behavior, target_user, hybrid_recommendation
from utils.pagination import StandardResultsSetPagination
from utils.tree import PermissionTree
from utils.view import MineApiViewSet, MineModelViewSet
import pandas as pd
from sklearn.linear_model import LinearRegression
import numpy as np
from django.db.models import Count, Q, Avg, Sum, F
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

from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import seasonal_decompose
from sklearn.ensemble import IsolationForest
import pandas as pd

charts_dir = os.path.join('media', 'charts')
if not os.path.exists(charts_dir):
    os.makedirs(charts_dir)

class LoginView(MineApiViewSet):
    authentication_classes = []
    permission_classes = []

    @swagger_auto_schema(
        request_body=LoginSerializer,  # 指定请求体的序列化器
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
        security=[],  # 表示不需要认证即可访问该接口
        operation_summary="用户登录并获取JWT Token",
        operation_description="通过用户名和密码进行登录，如果成功则返回一个JWT Token"
    )
    def post(self, request):
        # 1. 表单校验
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        # 2. 用户名+密码验证
        user_object = User.objects.filter(**ser.data).first()
        if not user_object:
            raise ValidationError({'message': ["用户名或密码错误"]})

        # 3. 生成jwt token
        token = jwt.encode(
            payload={
                'id': user_object.id,
                'username': user_object.username,
                'exp': timezone.now() + timezone.timedelta(days=7),
                "is_super": user_object.is_super,  # 将 is_super 字段加入 Payload
            },
            key=settings.SECRET_KEY,
            algorithm="HS256",
            headers={
                'typ': 'jwt',
                'alg': 'HS256'
            }
        )

        # 4. 获取用户权限并构建权限字典
        """
        if user_object.is_super:
            all_permissions = Permission.objects.all()
        else:
            all_permissions = Permission.objects.filter(role__users=user_object)
            print(all_permissions)
        """
        try:
            if user_object.is_super:
                all_permissions = Permission.objects.all()
            else:
                all_permissions = Permission.objects.filter(role__in=user_object.roles.all()).distinct()
        except Exception as e:
            print(f"Error fetching permissions: {e}")
            all_permissions = Permission.objects.none()  # 返回空查询集

        # 构建菜单权限字典
        menu_permissions_dict = {}
        for perm in all_permissions:
            for menu in perm.menu_set.all():
                if menu.id not in menu_permissions_dict:
                    menu_permissions_dict[menu.id] = []
                menu_permissions_dict[menu.id].append({
                    'route': perm.route,
                    'method': perm.method
                })
        # 5. 构建顶级菜单及其子菜单
        top_menus = Menu.objects.filter(parent_id__isnull=True).distinct()
        # 6. 构建权限字典
        route_method_dict = {}
        for row in all_permissions.values('route', 'method'):
            route = row['route']
            method = row['method']
            if route not in route_method_dict:
                route_method_dict[route] = set()  # 初始化为一个空集合
            route_method_dict[route].add(method)  # 将方法添加到集合中

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
    公告视图集，支持增删改查操作。
    """
    permission_classes = []
    queryset = Announcement.objects.all().order_by('-published_at')
    serializer_class = AnnouncementSerializer
    pagination_class = StandardResultsSetPagination
    # 移除默认过滤器设置，改为手动处理
    filter_backends = [DjangoFilterBackend]
    # 移除默认筛选字段，改为在get_queryset中手动处理
    # filterset_fields = ['title']
    @action(detail=True, methods=['patch'], url_path='toggle-visibility')
    def toggle_visibility(self, request, pk=None):
        """
        切换公告的可见性状态（上线/下线）
        """
        try:
            announcement = self.get_object()
            
            # 获取用户信息并判断是否为管理员
            user = request.user
            is_admin = False
            
            # 检查用户类型
            if hasattr(user, 'user_type') and user.user_type:
                user_type_value = user.user_type
                # 1 是图书管理员，2 是系统管理员
                if str(user_type_value) == '1' or user_type_value == 1 or str(user_type_value) == '2' or user_type_value == 2:
                    is_admin = True
            
            # 检查用户角色
            if not is_admin and hasattr(user, 'roles'):
                role_names = [role.name for role in user.roles.all()]
                if any(role in ['图书管理员', '系统管理员', 'admin', 'librarian'] for role in role_names):
                    is_admin = True
            
            # 检查是否是超级用户
            if not is_admin and getattr(user, 'is_superuser', False):
                is_admin = True
            
            # 如果不是管理员，返回权限错误
            if not is_admin:
                return Response(
                    {"error": "只有管理员可以执行此操作"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # 切换可见性状态
            announcement.is_visible = not announcement.is_visible
            announcement.save()
            
            # 返回更新后的状态
            serializer = self.get_serializer(announcement)
            return Response({
                "message": f"公告已{'上线' if announcement.is_visible else '下线'}",
                "is_visible": announcement.is_visible,
                "announcement": serializer.data
            })
            
        except Announcement.DoesNotExist:
            return Response(
                {"error": "未找到指定公告"}, 
                status=status.HTTP_404_NOT_FOUND
            )
    def create(self, request, *args, **kwargs):
        """
        创建公告
        添加标题重复检查
        """
        # 检查标题是否已存在
        title = request.data.get('title', '').strip()
        
        if not title:
            return Response(
                {"title": ["公告标题不能为空"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查标题是否重复
        if Announcement.objects.filter(title=title).exists():
            return Response(
                {"title": ["该公告标题已存在，请使用其他标题"]},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def get_queryset(self):
        """
        根据用户类型过滤公告
        """
        queryset = Announcement.objects.all().order_by('-published_at')
        
        # 获取用户信息并详细记录日志
        user = self.request.user
        print("===== 用户信息 =====")
        print(f"用户: {user}")
        print(f"用户类型: {getattr(user, 'user_type', 'Unknown')}")
        print(f"是否超级用户: {getattr(user, 'is_superuser', False)}")
        print(f"用户角色: {[role.name for role in user.roles.all()] if hasattr(user, 'roles') else []}")
        
        # 判断用户是否为管理员
        is_admin = False
        
        # 方法1：检查用户类型（如果用户类型字段已设置）
        if hasattr(user, 'user_type') and user.user_type:
            user_type_value = user.user_type
            # 1 是图书管理员，2 是系统管理员
            if str(user_type_value) == '1' or user_type_value == 1 or str(user_type_value) == '2' or user_type_value == 2:
                is_admin = True
        
        # 方法2：检查用户名（备用检查）
        if not is_admin and hasattr(user, 'username'):
            if user.username == 'admin' or user.username == 'librarian':
                is_admin = True
        
        # 方法3：检查用户角色
        if not is_admin and hasattr(user, 'roles'):
            role_names = [role.name for role in user.roles.all()]
            if any(role in ['图书管理员', '系统管理员', 'admin', 'librarian'] for role in role_names):
                is_admin = True
        
        # 方法4：检查是否是超级用户
        if not is_admin and getattr(user, 'is_superuser', False):
            is_admin = True
        
        # 兼容模式：同时保留URL参数检查，以便平滑过渡
        if not is_admin:
            user_type_param = self.request.query_params.get('user_type', None)
            is_librarian_param = self.request.query_params.get('is_librarian', 'false').lower() == 'true'
            if user_type_param in ['1', '2'] or is_librarian_param:
                is_admin = True
        
        print(f"是否管理员: {is_admin}")
        
        # 获取查询参数
        title = self.request.query_params.get('title', None)
        if title:
            queryset = queryset.filter(title__icontains=title)
        
        # 只有非管理员才过滤可见性
        if not is_admin:
            print("过滤: 只显示上线公告")
            queryset = queryset.filter(is_visible=True)
        else:
            print("不过滤: 显示所有公告（包括上线和下线）")
        
        return queryset

class BookViewSet(MineModelViewSet):
    """图书视图集"""
    permission_classes = []
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['title', 'category', 'author']
    def create(self, request, *args, **kwargs):
        """
        添加图书的实现：
        1. 检查图书标题、作者和分类是否为空
        2. 检查图书标题是否已存在
        3. 处理作者名称：查找或创建作者记录
        4. 处理分类名称：查找或创建分类记录
        """
        data = request.data.copy()
        
        # 1. 检查标题是否为空
        title = data.get('title')
        if not title or not title.strip():
            return Response(
                {"title": ["图书标题不能为空"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. 检查作者是否为空
        author_name = data.get('author')
        if not author_name or not str(author_name).strip():
            return Response(
                {"author": ["作者不能为空"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 3. 检查分类是否为空
        category_name = data.get('category')
        if not category_name or not str(category_name).strip():
            return Response(
                {"category": ["分类不能为空"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 4. 检查标题是否已存在
        if Book.objects.filter(title=title.strip()).exists():
            return Response(
                {"title": ["图书已存在"]}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # 5. 处理作者名称（查找或创建作者）
        if isinstance(author_name, str):
            author_obj, created = Author.objects.get_or_create(name=author_name.strip())
            data['author'] = author_obj.id
            
        # 6. 处理分类名称（查找或创建分类）
        if isinstance(category_name, str):
            category_obj, created = Category.objects.get_or_create(name=category_name.strip())
            data['category'] = category_obj.id
            
        # 7. 创建图书记录
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED, 
            headers=headers
        )

    @action(detail=False, methods=['GET'], url_path='top-rated')
    def prepare_recommendation_data(self, request, *args, **kwargs):
        """
        准备推荐所需的数据：
        - 当前用户的图书偏好：{"title": score...}
        - 可供选择的用户：[{"title": score...}, ...]
        """
        books_queryset = Book.objects.select_related('author', 'category').all()
        total_book_list = []
        for book in books_queryset:
            book_dict = {}
            book_dict['id'] = book.id
            book_dict['title'] = book.title
            book_dict['author_name']  = book.author.name
            book_dict['category_name']    = book.category.name
            book_dict['description'] = book.description
            total_book_list.append(book_dict)
            print("-" * 30)
        print('看看总数据%s'%total_book_list)
        # 获取用户输入的字符串（例如"科技类"）
        input_string = request.query_params.get('query', None)
        recommended_books = hybrid_recommendation(total_book_list, user_behavior, input_string, target_user)
        print({"recommended_books": recommended_books})
        return Response(recommended_books)


class BorrowRecordViewSet(MineModelViewSet):
    """借阅记录视图集"""
    permission_classes = []
    serializer_class = BorrowRecordSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status']

    def get_queryset(self):
        """
        普通用户只能查看自己的借阅记录，管理员可以查看所有记录。
        支持按用户、书名和类别查询。
        """
        queryset = BorrowRecord.objects.all()
        
        # 获取用户信息，判断是否为图书管理员
        user = self.request.user
        
        # 从前端参数获取admin身份 - 使用前端传来的is_admin参数
        is_admin_param = self.request.query_params.get('is_admin', 'false')
        is_librarian = is_admin_param.lower() == 'true'
        
        # 打印调试信息
        print(f"User: {user}, Username: {user.username}, ID: {user.id}")
        print(f"Query params: {self.request.query_params}")
        print(f"is_admin param: {is_admin_param}")
        print(f"Is Librarian: {is_librarian}")
        
        # 获取查询参数
        book_title = self.request.query_params.get('title', None)
        user_id = self.request.query_params.get('user_id', None)
        status = self.request.query_params.get('status', None)
        
        print(f"Book title: {book_title}")
        print(f"User ID: {user_id}")
        print(f"Status: {status}")
        
        # 非图书管理员只能查看自己的记录
        if not is_librarian and hasattr(user, 'id'):
            queryset = queryset.filter(user_id=user.id)
            print(f"Filtering for user_id: {user.id} (non-admin)")
        else:
            print("Not filtering by user_id - user is admin")
        
        # 根据查询参数过滤
        if book_title:
            queryset = queryset.filter(book__title__icontains=book_title)
            print(f"Filtering by book title: {book_title}")
        
        # 管理员可按用户过滤，非管理员不行
        if user_id and is_librarian:
            queryset = queryset.filter(user_id=user_id)
            print(f"Admin filtering for user_id: {user_id}")
        
        if status:
            queryset = queryset.filter(status=status)
            print(f"Filtering by status: {status}")
        
        # 打印最终查询结果数量
        record_count = queryset.count()
        print(f"Total records returned: {record_count}")
        
        return queryset
    def perform_create(self, serializer):
        """创建借阅记录时自动关联当前用户，并设置初始状态为pending"""
        # 获取当前用户
        user = self.request.user
        
        # 检查用户是否已认证（通过检查是否有id属性或类型是否是我们的User模型）
        if hasattr(user, 'id') and user.id is not None:
            # 设置初始状态为pending（待审批）
            record = serializer.save(user_id=user.id, status='pending')
        else:
            # 否则使用请求数据中的user_id，同样设置状态为pending
            record = serializer.save(status='pending')
            
        # 返回提示信息，让前端显示"申请借阅成功，待审批"
        return Response({
            "message": "申请借阅成功，请等待管理员审批",
            "status": "pending",
            "status_description": "借阅申请待审批", 
            "button_text": "待审批",
            "book_id": record.book.id,
            "book_title": record.book.title,
            "success": True,
            "action": "borrow_request"
        }, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """
        更新借阅记录
        支持普通用户申请归还（状态从borrowed变为approval）
        """
        # 获取要更新的对象
        instance = self.get_object()
        
        # 获取当前用户
        user = request.user
        
        # 获取请求中的状态
        requested_status = request.data.get('status', None)
        
        # 检查是否为归还申请（状态从borrowed变为approval）
        if requested_status == 'approval' and instance.status == 'borrowed':
            # 检查是否是本人操作
            if instance.user.id != user.id and not (hasattr(user, 'user_type') and (user.user_type == 1 or str(user.user_type) == '1')):
                return Response({"error": "您只能申请归还自己借阅的图书"}, 
                              status=status.HTTP_403_FORBIDDEN)
            
            # 更新状态为待审批归还
            instance.status = 'approval'
            instance.save()
            
            return Response({
                "message": "归还申请已提交，等待管理员审批",
                "status": "approval",
                "status_description": "归还申请待审批",
                "book_id": instance.book.id,
                "book_title": instance.book.title,
                "success": True
            })
        
        # 对于其他更新操作，使用默认的更新逻辑
        return super().update(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'], url_path='check-book-status')
    def check_book_status(self, request):
        """
        检查当前用户对特定图书的借阅状态
        """
        # 获取当前用户和请求的图书ID
        user = request.user
        book_id = request.query_params.get('book_id')
        
        if not book_id:
            return Response({"error": "必须提供图书ID"}, status=status.HTTP_400_BAD_REQUEST)
        
        # 状态描述映射 - 用户友好的描述文本
        status_descriptions = {
            'pending': '您的借阅申请正在等待管理员审批',
            'borrowed': '您已成功借阅此书',
            'returned': '您已归还此书',
            'rejected': '您的借阅申请被拒绝',
            'approval': '您的归还申请正在等待管理员审批'  # 添加归还申请状态描述
        }
        
        # 按钮文本映射 - 对应不同状态显示的按钮文字
        button_texts = {
            'pending': '待审批',
            'borrowed': '已借阅',
            'returned': '申请借阅',
            'rejected': '申请借阅',
            'available': '申请借阅',
            'approval': '待审批归还'  # 添加归还申请状态按钮文本
        }
        
        # 检查用户是否已认证
        if hasattr(user, 'id') and user.id is not None:
            latest_record = BorrowRecord.objects.filter(
                user_id=user.id,
                book_id=book_id
            ).order_by('-borrow_date').first()
            
            if latest_record:
                record_status = latest_record.status
                
                # 如果最新记录是"已归还"或"被拒绝"状态，并且是较早的记录，则视为可借阅
                if record_status in ['returned', 'rejected']:
                        return Response({
                            "book_id": book_id,
                            "status": "available",
                            "status_description": "此书可以借阅",
                            "button_text": "申请借阅",
                            "can_borrow": True
                        })
                
                response_data = {
                    "book_id": book_id,
                    "status": record_status,
                    "record_id": latest_record.id,
                    "borrow_date": latest_record.borrow_date,
                    "status_description": status_descriptions.get(record_status, "未知状态"),
                    "button_text": button_texts.get(record_status, "申请借阅"),
                    "can_borrow": record_status in ['returned', 'rejected'],
                }
                
                # 如果有归还日期且状态为borrowed，显示归还日期
                if latest_record.return_date and record_status == 'borrowed':
                    response_data["return_date"] = latest_record.return_date
                    response_data["expected_return_date"] = latest_record.return_date
                    # 计算剩余天数
                    today = timezone.now().date()
                    return_date = latest_record.return_date.date()
                    days_remaining = (return_date - today).days
                    response_data["days_remaining"] = days_remaining 
                    response_data["return_date_info"] = f"应在 {return_date.strftime('%Y-%m-%d')} 前归还"
                
                return Response(response_data)
            
        # 如果没有记录或用户未认证，则图书可借阅
        return Response({
            "book_id": book_id,
            "status": "available",
            "status_description": "此书可以借阅",
            "button_text": "申请借阅",
            "can_borrow": True
        })
    
    @action(detail=False, methods=['get'], url_path='pending-approvals')
    def pending_approvals(self, request):
        """
        获取所有待审批的借阅申请
        """
        # 检查用户是否为图书管理员
        user = request.user
        is_librarian = False
        if hasattr(user, 'user_type'):
            user_type_value = user.user_type
            if str(user_type_value) == '1' or user_type_value == 1:
                is_librarian = True
        
        if not is_librarian:
            return Response({"error": "只有图书管理员可以查看待审批的借阅申请"}, 
                           status=status.HTTP_403_FORBIDDEN)
        
        # 获取所有pending状态的借阅记录
        pending_records = BorrowRecord.objects.filter(status='pending').order_by('-borrow_date')
        
        # 使用分页
        page = self.paginate_queryset(pending_records)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # 为每条记录添加操作按钮信息
            data = serializer.data
            for record in data:
                record['has_approve_buttons'] = True  # 添加标记，表示需要显示审批按钮
                record['approve_url'] = f"/api/borrow-records/{record['id']}/approve/"  # 添加审批URL
                record['can_approve'] = True  # 表明当前用户可以进行审批
            
            paginated_response = self.get_paginated_response(data)
            # 添加额外信息，确保前端知道显示审批按钮
            paginated_response.data['is_approval_list'] = True
            return paginated_response
        
        serializer = self.get_serializer(pending_records, many=True)
        data = serializer.data
        # 为每条记录添加操作按钮信息
        for record in data:
            record['has_approve_buttons'] = True  # 添加标记，表示需要显示审批按钮
            record['approve_url'] = f"/api/borrow-records/{record['id']}/approve/"  # 添加审批URL
            record['can_approve'] = True  # 表明当前用户可以进行审批
        
        return Response({
            "results": data,
            "is_approval_list": True,  # 添加标记，表示这是待审批列表
            "count": len(data)
        })
    @action(detail=True, methods=['post'], url_path='return')
    def return_book(self, request, pk=None):
        """
        用户归还图书
        """
        try:
            # 获取借阅记录
            borrow_record = self.get_object()
            # 检查记录状态是否为borrowed
            if borrow_record.status != 'borrowed':
                return Response({"error": "只有处于借阅中的图书才能归还"}, 
                            status=status.HTTP_400_BAD_REQUEST)
            
            # 更新借阅记录状态为已归还
            borrow_record.status = 'returned'
            borrow_record.save()
            
            # 更新图书可借阅状态
            book = borrow_record.book
            book.is_available = True
            book.save()
            
            # 构建简化的响应数据
            response_data = {
                "message": "图书已成功归还",
                "status": "returned",
                "book_id": borrow_record.book.id,
                "book_title": borrow_record.book.title,
                "button_text": "申请借阅"  # 归还后恢复为可借阅状态
            }
            
            return Response(response_data)
            
        except BorrowRecord.DoesNotExist:
            return Response({"error": "借阅记录不存在"}, status=status.HTTP_404_NOT_FOUND)


    @action(detail=True, methods=['post'], url_path='approve')
    def approve_borrow(self, request, pk=None):
        """
        管理员审批借阅申请或归还申请
        """
        # 检查用户是否为图书管理员
        user = request.user
        is_librarian = False
        if hasattr(user, 'user_type'):
            user_type_value = user.user_type
            if str(user_type_value) == '1' or user_type_value == 1:
                is_librarian = True
        
        # 从前端参数获取admin身份
        is_admin_param = request.query_params.get('is_admin', 'false').lower() == 'true'
        if is_admin_param:
            is_librarian = True
        
        if not is_librarian:
            return Response({"error": "只有图书管理员可以审批借阅申请"}, 
                        status=status.HTTP_403_FORBIDDEN)
        
        try:
            # 获取借阅记录
            borrow_record = self.get_object()
            
            # 获取审批决定
            approval_status = request.data.get('status')
            
            # 处理借阅申请
            if borrow_record.status == 'pending':
                if approval_status not in ['borrowed', 'rejected']:
                    return Response({"error": "审批借阅状态必须是 'borrowed' (同意) 或 'rejected' (拒绝)", "success": False}, 
                                status=status.HTTP_400_BAD_REQUEST)
                
                # 更新借阅记录状态
                borrow_record.status = approval_status
                
                # 如果批准借阅，设置预期归还日期并更新图书可借阅状态
                if approval_status == 'borrowed':
                    # 默认借阅期限为30天
                    borrow_record.return_date = timezone.now() + timezone.timedelta(days=15)
                    
                    # 更新图书状态为不可借阅
                    book = borrow_record.book
                    book.is_available = False
                    book.save()
                
                borrow_record.save()
                
                # 构建简化的响应，便于前端显示
                response_data = {
                    "message": "借阅申请已" + ("批准" if approval_status == 'borrowed' else "拒绝"),
                    "status": approval_status,
                    "success": True,
                    "book_id": borrow_record.book.id,
                    "book_title": borrow_record.book.title,
                    "record_id": borrow_record.id,
                    "user_id": borrow_record.user.id,
                    "username": borrow_record.user.username,
                    "button_text": "已借阅" if approval_status == 'borrowed' else "借阅",
                    "action_type": "approve_borrow",
                    "refresh_needed": True  # 通知前端刷新借阅记录列表
                }
                
                # 如果已批准，添加归还日期
                if approval_status == 'borrowed':
                    response_data["expected_return_date"] = borrow_record.return_date
                
                return Response(response_data)
            
            # 处理归还申请 - 归还申请只能同意，不能拒绝
            elif borrow_record.status == 'approval':
                # 更新借阅记录状态为已归还
                borrow_record.status = 'returned'
                
                # 更新图书可借阅状态
                book = borrow_record.book
                book.is_available = True
                book.save()
                
                borrow_record.save()
                
                # 构建响应
                response_data = {
                    "message": "归还申请已批准",
                    "status": 'returned',
                    "success": True,
                    "book_id": borrow_record.book.id,
                    "book_title": borrow_record.book.title,
                    "record_id": borrow_record.id,
                    "user_id": borrow_record.user.id,
                    "username": borrow_record.user.username,
                    "button_text": "申请借阅",
                    "action_type": "approve_return",
                    "refresh_needed": True
                }
                
                return Response(response_data)
            
            else:
                return Response({"error": f"无法审批当前状态为 '{borrow_record.status}' 的记录", "success": False}, 
                            status=status.HTTP_400_BAD_REQUEST)
            
        except BorrowRecord.DoesNotExist:
            return Response({"error": "借阅记录不存在", "success": False}, status=status.HTTP_404_NOT_FOUND)
class RecommendationViewSet(MineModelViewSet):
    """推荐视图集（只读）
    """
    authentication_classes = []
    permission_classes = []
    queryset = Recommendation.objects.all()
    serializer_class = RecommendationSerializer

    def get_queryset(self):
        """普通用户只能查看自己的推荐结果
        """
        user = self.request.user
        return Recommendation.objects.filter(user=user)
    @action(detail=False, methods=['get'], url_path="popular_books_analysis")
    def popular_books_analysis(self, request):
        """
        热门类别分析接口：分析哪些图书类别最受欢迎，并可选择性添加AI总结
        :param request: 包含 top_n 参数和 add_ai_summary 参数
        :return: JSON 数据，包含适合BI图表展示的格式
        """
        # 获取参数
        top_n = int(self.request.GET.get('top_n', 5))  # 默认展示前5个热门类别
        add_ai_summary = self.request.GET.get('add_ai_summary', 'false').lower() == 'true'  # 是否添加AI总结
        
        # 按类别统计借阅次数
        category_stats = (
            BorrowRecord.objects.filter(status='borrowed')
            .values('book__category__id', 'book__category__name')
            .annotate(borrow_count=Count('id'))
            .order_by('-borrow_count')
        )
        
        # 处理可能存在的空类别
        categories = []
        for stat in category_stats:
            category_name = stat['book__category__name'] or "未分类"
            categories.append({
                "category_id": stat['book__category__id'],
                "category_name": category_name,
                "borrow_count": stat['borrow_count'],
                "percentage": 0  # 先初始化为0，稍后计算
            })
        
        # 计算总借阅量
        total_borrows = sum(cat['borrow_count'] for cat in categories)
        
        # 计算每个类别的借阅百分比
        if total_borrows > 0:
            for category in categories:
                category['percentage'] = round((category['borrow_count'] / total_borrows) * 100, 2)
        
        # 只保留top_n个类别
        top_categories = categories[:top_n]
        
        # 获取每个类别下的热门书籍
        for category in top_categories:
            category_name = category['category_name']
            
            # 查询该类别下的热门书籍
            top_books_in_category = (
                BorrowRecord.objects.filter(
                    status='borrowed',
                    book__category__name=category_name if category_name != "未分类" else None
                )
                .values('book__id', 'book__title')
                .annotate(borrow_count=Count('id'))
                .order_by('-borrow_count')[:3]  # 每个类别取前3本热门书
            )
            
            # 添加到类别数据中
            category['top_books'] = [
                {
                    "book_id": book['book__id'],
                    "book_title": book['book__title'],
                    "borrow_count": book['borrow_count']
                }
                for book in top_books_in_category
            ]
        
        # AI总结（如果请求中要求添加）
        ai_summary = None
        if add_ai_summary and categories:
            # 生成AI总结
            most_popular = categories[0]['category_name']
            total_categories = len(categories)
            top_three = [cat['category_name'] for cat in categories[:3]] if len(categories) >= 3 else [cat['category_name'] for cat in categories]
            
            # 构建总结文本 (修复中文引号问题)
            summary_text = f"根据分析，在所有{total_categories}个图书类别中，\"{most_popular}\"类是最受欢迎的，占总借阅量的{categories[0]['percentage']}%。"
            
            if len(top_three) >= 3:
                summary_text += f" 排名前三的热门类别分别是：{top_three[0]}、{top_three[1]}和{top_three[2]}，"
                total_percentage = sum(cat['percentage'] for cat in categories[:3])
                summary_text += f"它们共占借阅总量的{round(total_percentage, 2)}%。"
            
            # 分析趋势和读者兴趣 (修复中文引号问题)
            if categories[0]['percentage'] > 40:
                summary_text += f" 读者对\"{most_popular}\"类图书有明显的偏好，建议图书馆增加此类图书的采购数量。"
            elif total_categories > 5 and categories[4]['percentage'] > 10:
                summary_text += " 读者兴趣比较多样化，前五大类别都有相当数量的借阅，建议图书馆保持均衡的图书类别分布。"
            
            ai_summary = {
                "text": summary_text,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "data_based_on": f"基于{total_borrows}次借阅记录的分析"
            }
        
        # 准备适合BI图表的数据格式
        chart_data = {
            "pie_chart": {
                "title": "图书类别借阅分布",
                "series": [{
                    "name": "借阅数量",
                    "data": [{"name": cat["category_name"], "value": cat["borrow_count"]} for cat in top_categories]
                }]
            },
            "bar_chart": {
                "title": "热门图书类别分析",
                "xAxis": {"data": [cat["category_name"] for cat in top_categories]},
                "series": [{
                    "name": "借阅次数",
                    "type": "bar",
                    "data": [cat["borrow_count"] for cat in top_categories]
                }]
            },
            "percentage_chart": {
                "title": "借阅百分比分布",
                "series": [{
                    "name": "占比",
                    "data": [{"name": cat["category_name"], "value": cat["percentage"]} for cat in top_categories]
                }]
            }
        }
        
        # 返回JSON数据
        response_data = {
            "top_categories": top_categories,
            "total_borrows": total_borrows,
            "categories_count": len(categories),
            "chart_data": chart_data
        }
        
        # 如果请求了AI总结，则添加到响应中
        if ai_summary:
            response_data["ai_summary"] = ai_summary
        
        return Response(response_data)

    @action(detail=False, methods=['get'], url_path="predictive_analysis")
    def predictive_analysis(self, request):
        """
        预测性分析接口 - 使用ARIMA模型预测未来借阅量
        :param request: 包含 future_days 参数
        :return: JSON 数据，包含适合BI图表展示的格式
        """
        future_days = int(self.request.GET.get('future_days', 30))  # 默认预测未来30天
        
        try:
            records = BorrowRecord.objects.filter(status='borrowed').values_list('borrow_date', flat=True)
            
            if not records:
                return Response({'error': '没有足够的历史借阅数据用于预测'}, status=400)
                
            dates = [record.date() for record in records]
            unique_dates = sorted(set(dates))
            date_counts = {date: dates.count(date) for date in unique_dates}
            
            date_range = pd.date_range(start=min(unique_dates), end=max(unique_dates))
            ts_data = [date_counts.get(date.date(), 0) for date in date_range]
            
            ts = pd.Series(ts_data, index=date_range)
            
            # 自动确定ARIMA参数 (p,d,q)
            # 简化起见，使用固定参数，实际应用中可以通过AIC/BIC评分自动选择最优参数
            # 使用(5,1,0)作为默认参数 - 可根据数据特性调整
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
                            "name": "预测借阅量",
                            "type": "line",
                            "data": [None] * len(historical_counts) + predicted_counts,
                            "itemStyle": {"color": "#ff4d4f"},
                            "lineStyle": {"type": "dashed"}
                        }
                    ],
                    "legend": {
                        "data": ["预测借阅量"]
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
                'error': f'预测过程中发生错误: {str(e)}',
                'suggestion': '可能需要更多数据点来进行可靠的ARIMA预测'
            }, status=500)

class CategoryViewSet(MineModelViewSet):
    """图书分类视图集（只读）
    """
    permission_classes = []
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = StandardResultsSetPagination


class AuthorViewSet(MineModelViewSet):
    """作者信息视图集（只读）
    获取作者
    """
    permission_classes = []
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    pagination_class = StandardResultsSetPagination


class UserViewSet(MineModelViewSet):
    permission_classes = []
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['username']
    
    @action(detail=False, methods=['GET'], url_path='user-types')
    def get_user_types(self, request):
        """
        获取所有可用的用户类型，用于前端创建用户时选择
        """
        user_types = [{'value': key, 'label': value} for key, value in User.user_type_choices]
        return Response(user_types)
    
    def create(self, request, *args, **kwargs):
        """
        创建用户并根据用户类型分配对应的角色和权限
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        
        user = serializer.save()
        
        
        user_type = user.user_type
        
        
        role_name_map = {
            '0': '读者',        
            0: '读者',          
            '1': '图书管理员',   
            1: '图书管理员',   
            '2': '系统管理员',   
            2: '系统管理员'     
        }
        role_name = role_name_map.get(user_type)
        
        if role_name:
            try:
                role = Role.objects.filter(name=role_name).first()
                if role:
                    user.roles.add(role)
                else:
                    print(f"Warning: 未找到名为 '{role_name}' 的角色")
            except Exception as e:
                print(f"Error: 分配角色时发生错误 - {str(e)}")
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    
    def update(self, request, *args, **kwargs):
        """
        更新用户并根据用户类型更新对应的角色和权限
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # 保存更新后的用户数据
        user = serializer.save()
        
        # 检查是否更新了用户类型
        if 'user_type' in request.data:
            # 获取用户类型
            user_type = user.user_type
            
            # 根据用户类型分配角色
            role_name_map = {
                '0': '读者',        # 读者角色
                0: '读者',          # 读者角色
                '1': '图书管理员',    # 图书管理员角色
                1: '图书管理员',      # 图书管理员角色
                '2': '系统管理员',    # 系统管理员角色
                2: '系统管理员'       # 系统管理员角色
            }
            
            # 获取对应的角色名称
            role_name = role_name_map.get(user_type)
            
            if role_name:
                try:
                    # 移除现有角色
                    user.roles.clear()
                    
                    # 查找对应角色
                    role = Role.objects.filter(name=role_name).first()
                    if role:
                        # 分配角色给用户
                        user.roles.add(role)
                    else:
                        # 如果角色不存在，可以考虑自动创建角色
                        print(f"Warning: 未找到名为 '{role_name}' 的角色")
                except Exception as e:
                    print(f"Error: 更新角色时发生错误 - {str(e)}")
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
            
        return Response(serializer.data)
    permission_classes = []
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['username']
    
    @action(detail=False, methods=['GET'], url_path='user-types')
    def get_user_types(self, request):
        """
        获取所有可用的用户类型，用于前端创建用户时选择
        """
        user_types = [{'value': key, 'label': value} for key, value in User.user_type_choices]
        return Response(user_types)

    def perform_create(self, serializer):
        """
        创建用户后根据用户类型分配相应的角色
        """
        # 创建用户
        user = serializer.save()
        
        # 获取用户类型
        user_type = user.user_type
        
        # 根据用户类型查找对应角色名称
        role_name = None
        for key, value in User.user_type_choices:
            if str(key) == str(user_type):
                role_name = value
                break
        
        # 分配角色
        if role_name:
            try:
                role = Role.objects.get(name=role_name)
                user.roles.add(role)
            except Role.DoesNotExist:
                # 如果角色不存在，则不分配角色
                pass