import time
from django.test import TestCase, Client
from django.urls import reverse
from api.models import Book, Category, Author, BorrowRecord
from django.contrib.auth import get_user_model
import concurrent.futures
import statistics
from django.db import connection

User = get_user_model()

class PerformanceTest(TestCase):
    """测试API的性能"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建测试用户
        self.client = Client()
        self.user = User.objects.create_user(
            username="perftest",
            email="perf@example.com",
            password="password123"
        )
        
        # 创建管理员用户
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="admin123",
            is_staff=True
        )
        
        # 创建测试分类
        self.category = Category.objects.create(name="Performance Test")
        
        # 创建测试作者
        self.author = Author.objects.create(name="Performance Author")
        
        # 创建多本测试图书
        for i in range(50):
            Book.objects.create(
                title=f"Performance Book {i}",
                category=self.category,
                author=self.author,
                description=f"Performance test book {i}",
                is_available=True
            )
            
        # 登录用户
        self.client.login(username="perftest", password="password123")
        
        # 准备API端点
        self.books_url = reverse('book-list')
    
    def test_api_response_time(self):
        """测试API的响应时间"""
        # 记录开始时间
        start_time = time.time()
        
        # 发送请求
        response = self.client.get(self.books_url)
        
        # 计算响应时间
        response_time = time.time() - start_time
        
        # 验证响应成功
        self.assertEqual(response.status_code, 200)
        
        # 验证响应时间在合理范围内（通常应该小于1秒）
        self.assertLess(response_time, 1.0)
        
        # 打印响应时间以便记录
        print(f"API响应时间: {response_time:.4f} 秒")
    
    def test_concurrent_requests(self):
        """测试API处理并发请求的能力"""
        # 测试的请求数
        num_requests = 10
        
        # 存储每个请求的响应时间
        response_times = []
        
        # 记录数据库查询次数
        initial_queries = len(connection.queries)
        
        def make_request():
            """发送一个请求并测量响应时间"""
            start_time = time.time()
            client = Client()
            client.login(username="perftest", password="password123")
            response = client.get(self.books_url)
            end_time = time.time()
            return {
                'time': end_time - start_time,
                'status': response.status_code
            }
        
        # 使用线程池并发发送请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
            results = list(executor.map(lambda _: make_request(), range(num_requests)))
        
        # 记录完成后的数据库查询次数
        final_queries = len(connection.queries)
        
        # 验证所有请求都成功
        for result in results:
            self.assertEqual(result['status'], 200)
            response_times.append(result['time'])
        
        # 计算平均响应时间和中位数响应时间
        avg_time = sum(response_times) / len(response_times)
        median_time = statistics.median(response_times)
        max_time = max(response_times)
        min_time = min(response_times)
        
        # 打印性能测试结果
        print(f"\n并发测试结果 ({num_requests} 个并发请求):")
        print(f"平均响应时间: {avg_time:.4f} 秒")
        print(f"中位数响应时间: {median_time:.4f} 秒")
        print(f"最大响应时间: {max_time:.4f} 秒")
        print(f"最小响应时间: {min_time:.4f} 秒")
        print(f"数据库查询总数: {final_queries - initial_queries}")
        
        # 验证平均响应时间在合理范围内（通常不应超过2秒）
        self.assertLess(avg_time, 2.0)
    
    def test_database_performance(self):
        """测试数据库操作的性能"""
        # 记录初始查询次数
        reset_queries()
        initial_queries = len(connection.queries)
        
        # 执行大量的数据库查询
        start_time = time.time()
        books = Book.objects.filter(title__contains="Book").select_related('author', 'category')
        books_list = list(books)  # 强制执行查询
        query_time = time.time() - start_time
        
        # 记录最终查询次数
        final_queries = len(connection.queries)
        
        # 打印数据库性能测试结果
        print(f"\n数据库查询性能:")
        print(f"查询执行时间: {query_time:.4f} 秒")
        print(f"检索到的记录数: {len(books_list)}")
        print(f"执行的查询数: {final_queries - initial_queries}")
        
        # 验证查询时间在合理范围内
        self.assertLess(query_time, 0.5)
        
        # 测试批量创建的性能
        start_time = time.time()
        
        # 准备批量创建的数据
        new_books = []
        for i in range(20):
            new_books.append(Book(
                title=f"Bulk Book {i}",
                category=self.category,
                author=self.author,
                description=f"Bulk created book {i}",
                is_available=True
            ))
        
        # 批量创建
        Book.objects.bulk_create(new_books)
        bulk_create_time = time.time() - start_time
        
        # 打印批量创建性能结果
        print(f"批量创建 20 本书的时间: {bulk_create_time:.4f} 秒")
        
        # 验证批量创建时间在合理范围内
        self.assertLess(bulk_create_time, 1.0)


def reset_queries():
    """重置Django数据库查询日志"""
    connection.queries_log.clear() 