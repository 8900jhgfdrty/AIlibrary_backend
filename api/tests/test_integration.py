from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from api.models import Book, Category, Author, BorrowRecord
import json
from datetime import datetime, timedelta
from django.utils import timezone

User = get_user_model()

class LibrarySystemIntegrationTest(TestCase):
    """集成测试类 - 测试图书馆管理系统的核心流程"""
    
    def setUp(self):
        """
        测试前的准备工作：
        1. 创建测试用户（普通用户和图书管理员）
        2. 创建测试数据（图书分类、作者、图书）
        3. 初始化API客户端
        """
        # 创建API客户端
        self.client = APIClient()
        
        # 创建普通用户
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        
        # 创建图书管理员用户（librarian）
        self.librarian = User.objects.create_user(
            username='librarian',
            email='librarian@example.com',
            password='password123',
            is_staff=True
        )
        
        # 创建测试分类
        self.category = Category.objects.create(name="Science Fiction")
        
        # 创建测试作者
        self.author = Author.objects.create(name="Isaac Asimov")
        
        # 创建测试图书
        self.book = Book.objects.create(
            title="Foundation",
            category=self.category,
            author=self.author,
            description="A science fiction novel",
            is_available=True
        )
        
        # API端点URL
        self.books_url = reverse('book-list')
        self.borrow_url = reverse('borrow-record-list')
    
    def test_full_book_management_flow(self):
        """
        测试完整的图书管理流程：
        1. 管理员登录
        2. 创建新图书
        3. 更新图书信息
        4. 检索图书信息
        5. 删除图书
        """
        # 1. 管理员登录
        self.client.force_authenticate(user=self.librarian)
        
        # 2. 创建新图书
        new_book_data = {
            "title": "Dune",
            "author": "Frank Herbert",
            "category": "Science Fiction",
            "description": "A science fiction masterpiece"
        }
        
        create_response = self.client.post(self.books_url, new_book_data, format='json')
        
        # 验证图书创建成功
        self.assertEqual(create_response.status_code, status.HTTP_200_OK)
        self.assertEqual(create_response.data['data']['title'], "Dune")
        self.assertTrue(Book.objects.filter(title="Dune").exists())
        
        new_book_id = create_response.data['data']['id']
        
        # 3. 更新图书信息
        update_data = {
            "description": "A science fiction masterpiece about a desert planet"
        }
        
        update_url = reverse('book-detail', args=[new_book_id])
        update_response = self.client.patch(update_url, update_data, format='json')
        
        # 验证图书更新成功
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            update_response.data['description'], 
            "A science fiction masterpiece about a desert planet"
        )
        
        # 4. 检索图书信息
        retrieve_response = self.client.get(update_url)
        
        # 验证图书检索成功
        self.assertEqual(retrieve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieve_response.data['title'], "Dune")
        
        # 5. 删除图书
        delete_response = self.client.delete(update_url)
        
        # 验证图书删除成功
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(title="Dune").exists())

    def test_complete_borrow_return_flow(self):
        """
        测试完整的借阅和归还流程：
        1. 用户登录
        2. 用户发起借阅请求
        3. 管理员审批借阅请求
        4. 用户归还图书
        5. 管理员确认归还
        """
        # 1. 用户登录并发起借阅请求
        self.client.force_authenticate(user=self.user)
        
        borrow_data = {
            "book": self.book.id
        }
        
        borrow_response = self.client.post(self.borrow_url, borrow_data, format='json')
        
        # 验证借阅请求创建成功
        self.assertEqual(borrow_response.status_code, status.HTTP_200_OK)
        self.assertEqual(borrow_response.data.get('status'), 'pending')
        
        # 获取借阅记录ID
        borrow_id = borrow_response.data.get('id', None)
        if not borrow_id:
            # 如果响应结构不同，尝试从数据库获取
            borrow_record = BorrowRecord.objects.filter(
                user_id=self.user.id, 
                book_id=self.book.id,
                status='pending'
            ).first()
            borrow_id = borrow_record.id
        
        # 2. 管理员登录并审批借阅请求
        self.client.force_authenticate(user=self.librarian)
        
        approve_url = reverse('borrow-record-approve-borrow', kwargs={'pk': borrow_id})
        approve_data = {
            "status": "borrowed",
            "return_date": (timezone.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        }
        
        approve_response = self.client.post(approve_url, approve_data, format='json')
        
        # 验证借阅审批成功
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # 验证图书状态已更新为不可用
        updated_book = Book.objects.get(id=self.book.id)
        self.assertFalse(updated_book.is_available)
        
        # 3. 用户申请归还图书
        self.client.force_authenticate(user=self.user)
        
        return_url = reverse('borrow-record-return-book', kwargs={'pk': borrow_id})
        return_response = self.client.post(return_url, {}, format='json')
        
        # 验证归还请求成功
        self.assertEqual(return_response.status_code, status.HTTP_200_OK)
        
        # 4. 管理员确认归还
        self.client.force_authenticate(user=self.librarian)
        
        # 在当前API设计中，归还确认是通过approve_borrow实现的，所以复用approve_url
        confirm_response = self.client.post(approve_url, {"status": "returned"}, format='json')
        
        # 验证确认归还成功
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        
        # 验证图书状态已更新为可用
        updated_book = Book.objects.get(id=self.book.id)
        self.assertTrue(updated_book.is_available)
        
        # 验证借阅记录状态已更新为已归还
        updated_record = BorrowRecord.objects.get(id=borrow_id)
        self.assertEqual(updated_record.status, 'returned')

    def test_edge_cases_and_validations(self):
        """
        测试边界情况和验证逻辑：
        1. 尝试借阅不存在的图书
        2. 尝试借阅已借出的图书
        3. 非管理员尝试审批借阅请求
        4. 尝试归还未借阅的图书
        """
        # 1. 尝试借阅不存在的图书
        self.client.force_authenticate(user=self.user)
        
        invalid_borrow_data = {
            "book": 9999  # 不存在的图书ID
        }
        
        invalid_response = self.client.post(self.borrow_url, invalid_borrow_data, format='json')
        
        # 验证请求被拒绝
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # 2. 先成功借阅一本书
        valid_borrow_data = {
            "book": self.book.id
        }
        
        valid_response = self.client.post(self.borrow_url, valid_borrow_data, format='json')
        self.assertEqual(valid_response.status_code, status.HTTP_200_OK)
        
        # 管理员审批借阅
        self.client.force_authenticate(user=self.librarian)
        
        borrow_record = BorrowRecord.objects.filter(
            user_id=self.user.id, 
            book_id=self.book.id,
            status='pending'
        ).first()
        
        approve_url = reverse('borrow-record-approve-borrow', kwargs={'pk': borrow_record.id})
        approve_data = {
            "status": "borrowed",
            "return_date": (timezone.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        }
        
        self.client.post(approve_url, approve_data, format='json')
        
        # 更新图书状态为已借出
        self.book.is_available = False
        self.book.save()
        
        # 再次尝试借阅同一本书（现在已借出）
        self.client.force_authenticate(user=self.user)
        duplicate_response = self.client.post(self.borrow_url, valid_borrow_data, format='json')
        
        # 验证系统允许提交借阅请求（但会进入等待状态）
        self.assertEqual(duplicate_response.status_code, status.HTTP_200_OK)
        
        # 3. 非管理员尝试审批借阅请求
        new_borrow_record = BorrowRecord.objects.filter(
            user_id=self.user.id, 
            book_id=self.book.id,
            status='pending'
        ).last()
        
        self.client.force_authenticate(user=self.user)  # 普通用户
        
        approve_url = reverse('borrow-record-approve-borrow', kwargs={'pk': new_borrow_record.id})
        unauthorized_response = self.client.post(approve_url, approve_data, format='json')
        
        # 验证请求被拒绝（无权限）
        self.assertEqual(unauthorized_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # 4. 尝试归还未借阅的图书（创建新的未借阅图书）
        new_book = Book.objects.create(
            title="New Book",
            category=self.category,
            author=self.author,
            description="A new book",
            is_available=True
        )
        
        return_url = reverse('borrow-record-return-book', kwargs={'pk': 9999})  # 不存在的借阅记录ID
        invalid_return_response = self.client.post(return_url, {}, format='json')
        
        # 验证请求被拒绝
        self.assertEqual(invalid_return_response.status_code, status.HTTP_404_NOT_FOUND) 