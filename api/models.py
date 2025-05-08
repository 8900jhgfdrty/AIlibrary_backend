from django.db import models
from django.utils import timezone


class Permission(models.Model):
    """Permission table
    Permission model
    """
    name = models.CharField(verbose_name="Name", max_length=32)  # permission description
    route = models.CharField(verbose_name="Route Name", max_length=32)
    method = models.CharField(verbose_name="HTTP Method", max_length=32, null=True, blank=True)

    class Meta:
        db_table = 'permission'
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        ordering = ['-id']


class Role(models.Model):
    """Role model"""
    name = models.CharField(verbose_name="Role", max_length=32)
    permissions = models.ManyToManyField(verbose_name="Permissions", to="Permission")

    class Meta:
        db_table = 'role'
        verbose_name = "Role"
        verbose_name_plural = "Roles"
        ordering = ['-id']


class Menu(models.Model):
    """Menu table"""
    title = models.CharField(max_length=255, verbose_name="Title")
    name = models.CharField(max_length=255, verbose_name="Name")
    parent_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Parent ID")
    icon = models.CharField(max_length=255, blank=True, null=True, verbose_name="Icon")

    pers = models.ManyToManyField(verbose_name="Permissions", to="Permission", blank=True)
    # e.g., return all permissions for 'Announcement Management' (CRUD)
    class Meta:
        db_table = 'menu'
        verbose_name = 'Menu'
        verbose_name_plural = 'Menus'
        ordering = ['-id']

    def __str__(self):
        return self.title

class UserType(models.IntegerChoices):
    READER = 0, 'Reader'
    LIBRARIAN = 1, 'Librarian'
    SYSTEM_ADMIN = 2, 'System Administrator'

class User(models.Model):
    user_type = models.IntegerField(
    choices=UserType.choices, 
    default=UserType.READER,
    verbose_name="User Type")

    username = models.CharField(verbose_name="Username", max_length=32)
    password = models.CharField(verbose_name="Password", max_length=64)
    is_super = models.BooleanField(verbose_name="Is Superuser", default=False)
    roles = models.ManyToManyField(verbose_name="Roles", to="Role", blank=True)
    user_type = models.IntegerField(choices=UserType.choices, default=UserType.READER, verbose_name="User Type")
    is_active = models.BooleanField(verbose_name="Is Active", default=True)
    last_login = models.DateTimeField(verbose_name="Last Login", blank=True, null=True)

    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-id']

    def __str__(self):
        return f"{self.username} - {self.get_user_type_display()}"

    # Add these two methods here
    @property
    def is_authenticated(self):
        """
        Always return True. Used to distinguish authenticated users from AnonymousUser
        This is required by Django authentication system
        """
        return True
    
    @property
    def is_anonymous(self):
        """
        Always return False. Used to distinguish authenticated users from AnonymousUser
        This is required by Django authentication system
        """
        return False

class WhitelistUrl(models.Model):
    """Stores URLs that can be accessed without authentication."""
    url_pattern = models.CharField(max_length=255, unique=True, help_text="URL pattern or name")
    description = models.TextField(blank=True, null=True, help_text="Description of this whitelist URL")

    def __str__(self):
        return self.url_pattern

    class Meta:
        db_table = 'white_list_url'
        verbose_name = "Whitelist URL"
        verbose_name_plural = "Whitelist URLs"
        ordering = ['-id']


class Dictionary(models.Model):
    """Dictionary management"""
    key = models.CharField(max_length=100, unique=True, verbose_name="Key")
    value = models.TextField(verbose_name="Value")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    sort_order = models.IntegerField(default=0, verbose_name="Sort Order")
    STATUS_CHOICES = (
        (0, 'Inactive'),
        (1, 'Active'),
    )
    status = models.IntegerField(choices=STATUS_CHOICES, default=1, verbose_name="Status")
    created_time = models.DateTimeField(auto_now_add=True, verbose_name="Created Time")
    updated_time = models.DateTimeField(auto_now=True, verbose_name="Updated Time")

    class Meta:
        db_table = 'dictionary'
        verbose_name = "Dictionary"
        verbose_name_plural = "Dictionaries"
        ordering = ['sort_order', 'created_time']

    def __str__(self):
        return self.key


class Announcement(models.Model):
    """Announcement model"""
    title = models.CharField(max_length=255, verbose_name="Title")
    content = models.TextField(verbose_name="Content")
    is_visible = models.BooleanField(default=True, verbose_name="Is Visible")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")
    published_at = models.DateTimeField(default=timezone.now, verbose_name="Published At")

    class Meta:
        db_table = 'announcement'
        verbose_name = "Announcement"
        verbose_name_plural = "Announcements"
        ordering = ['-published_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Custom save method to ensure timestamps are updated on save
        """
        if not self.id:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def visible_status(self):
        """
        Returns the visibility status description
        """
        return "Visible" if self.is_visible else "Hidden"

    visible_status.short_description = "Visibility Status"


class Category(models.Model):
    """Book category"""
    name = models.CharField(max_length=255, verbose_name="Category Name")

    class Meta:
        db_table = 'category'
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Author(models.Model):
    """Author information"""
    name = models.CharField(max_length=255, verbose_name="Author Name")

    class Meta:
        db_table = 'author'
        verbose_name = "Author"
        verbose_name_plural = "Authors"

    def __str__(self):
        return self.name


class Book(models.Model):
    """Book information"""
    title = models.CharField(max_length=255, verbose_name="Title")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="books", verbose_name="Category")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books", verbose_name="Author")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    is_available = models.BooleanField(default=True, verbose_name="Is Available")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        db_table = 'book'
        verbose_name = "Book"
        verbose_name_plural = "Books"
        ordering = ['title']

    def __str__(self):
        return self.title


class BorrowRecord(models.Model):
    """Borrow record"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="borrow_records", verbose_name="User")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="borrow_records", verbose_name="Book")
    borrow_date = models.DateTimeField(auto_now_add=True, verbose_name="Borrow Date")
    return_date = models.DateTimeField(blank=True, null=True, verbose_name="Expected Return Date")
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")

    class Meta:
        db_table = 'borrow_record'
        verbose_name = "Borrow Record"
        verbose_name_plural = "Borrow Records"
        ordering = ['-borrow_date']

    def __str__(self):
        return f"{self.user.username} - {self.book.title}"


class Recommendation(models.Model):
    """Recommendation model"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recommendations", verbose_name="User")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="recommendations", verbose_name="Book")
    score = models.FloatField(verbose_name="Score", help_text="Recommendation score calculated by algorithm")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")

    class Meta:
        db_table = 'recommendation'
        verbose_name = "Recommendation"
        verbose_name_plural = "Recommendations"
        ordering = ['-score']

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.score})"


class Rating(models.Model):
    """书籍评分"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ratings", verbose_name="用户")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="ratings", verbose_name="图书")
    score = models.IntegerField(verbose_name="评分", help_text="范围：1-5")
    comment = models.TextField(blank=True, null=True, verbose_name="评论")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = 'rating'
        verbose_name = "评分"
        verbose_name_plural = verbose_name
        unique_together = ('user', 'book')  # 同一用户只能对同一本书评分一次
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.book.title} ({self.score})"
