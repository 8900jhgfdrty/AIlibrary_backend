from django.test import TestCase
from api.models import Book, Category, Author, BorrowRecord
from api.serializers import BookSerializer, CategorySerializer, AuthorSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class ModelTests(TestCase):
    """测试模型的基本功能"""
    
    def setUp(self):
        """设置测试数据"""
        self.category = Category.objects.create(name="Science Fiction")
        self.author = Author.objects.create(name="Isaac Asimov")
        self.book = Book.objects.create(
            title="Foundation",
            category=self.category,
            author=self.author,
            description="A science fiction novel",
            is_available=True
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
    
    def test_book_model_str(self):
        """测试图书模型的字符串表示"""
        self.assertEqual(str(self.book), "Foundation")
    
    def test_category_model_str(self):
        """测试分类模型的字符串表示"""
        self.assertEqual(str(self.category), "Science Fiction")
    
    def test_author_model_str(self):
        """测试作者模型的字符串表示"""
        self.assertEqual(str(self.author), "Isaac Asimov")
    
    def test_book_is_available_default(self):
        """测试图书默认为可用状态"""
        self.assertTrue(self.book.is_available)
    
    def test_book_serializer(self):
        """测试图书序列化器"""
        serializer = BookSerializer(self.book)
        data = serializer.data
        
        self.assertEqual(data['title'], "Foundation")
        self.assertEqual(data['author_name'], "Isaac Asimov")
        self.assertEqual(data['category_name'], "Science Fiction")
        
    def test_borrow_record_creation(self):
        """测试创建借阅记录"""
        borrow_record = BorrowRecord.objects.create(
            user=self.user,
            book=self.book,
            status="pending"
        )
        
        self.assertEqual(borrow_record.status, "pending")
        self.assertEqual(borrow_record.user, self.user)
        self.assertEqual(borrow_record.book, self.book)


class SerializerTests(TestCase):
    """测试序列化器的验证功能"""
    
    def setUp(self):
        """设置测试数据"""
        self.category = Category.objects.create(name="Science Fiction")
        self.author = Author.objects.create(name="Isaac Asimov")
        self.book_data = {
            "title": "",  # 空标题，应该无效
            "category": self.category.id,
            "author": self.author.id,
            "description": "A test book"
        }
        
    def test_book_serializer_validation(self):
        """测试图书序列化器的标题验证"""
        serializer = BookSerializer(data=self.book_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('title', serializer.errors)
        
    def test_category_serializer(self):
        """测试分类序列化器"""
        serializer = CategorySerializer(self.category)
        self.assertEqual(serializer.data['name'], "Science Fiction")
        
    def test_author_serializer(self):
        """测试作者序列化器"""
        serializer = AuthorSerializer(self.author)
        self.assertEqual(serializer.data['name'], "Isaac Asimov") 