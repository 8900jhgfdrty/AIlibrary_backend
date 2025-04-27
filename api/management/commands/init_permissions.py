from django.core.management.base import BaseCommand
from api.models import Permission, Role, User, Menu


class Command(BaseCommand):
    help = "Initialize system permissions and roles"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('正在初始化权限和角色...'))

        # define basic roles
        reader_role, _ = Role.objects.get_or_create(name="reader")
        librarian_role, _ = Role.objects.get_or_create(name="librarian")
        admin_role, _ = Role.objects.get_or_create(name="system_admin")

        # clear existing permission associations
        reader_role.permissions.clear()
        librarian_role.permissions.clear()
        admin_role.permissions.clear()

        # ----- define permissions -----

        # authentication permission
        login_perm, _ = Permission.objects.get_or_create(
            name="user login",
            route="login",
            method="post"
        )

        # ----- announcement permission -----
        view_announcement_perm, _ = Permission.objects.get_or_create(
            name="view announcement",
            route="announcement-list",
            method="get"
        )
        create_announcement_perm, _ = Permission.objects.get_or_create(
            name="create announcement",
            route="announcement-list",
            method="post"
        )
        view_announcement_detail_perm, _ = Permission.objects.get_or_create(
            name="view announcement detail",
            route="announcement-detail",
            method="get"
        )
        update_announcement_perm, _ = Permission.objects.get_or_create(
            name="update announcement",
            route="announcement-detail",
            method="put"
        )
        patch_announcement_perm, _ = Permission.objects.get_or_create(
            name="update announcement",
            route="announcement-detail",
            method="patch"
        )
        delete_announcement_perm, _ = Permission.objects.get_or_create(
            name="delete announcement",
            route="announcement-detail",
            method="delete"
        )
        toggle_announcement_perm, _ = Permission.objects.get_or_create(
            name="toggle announcement visibility",
            route="announcement-toggle-visibility",
            method="patch"
        )

        # ----- 图书权限 -----
        view_books_perm, _ = Permission.objects.get_or_create(
            name="view book list",
            route="book-list",
            method="get"
        )
        create_book_perm, _ = Permission.objects.get_or_create(
            name="create book",
            route="book-list",
            method="post"
        )
        view_book_detail_perm, _ = Permission.objects.get_or_create(
            name="view book detail",
            route="book-detail",
            method="get"
        )
        update_book_perm, _ = Permission.objects.get_or_create(
            name="update book",
            route="book-detail",
            method="put"
        )
        patch_book_perm, _ = Permission.objects.get_or_create(
            name="update book",
            route="book-detail",
            method="patch"
        )
        delete_book_perm, _ = Permission.objects.get_or_create(
            name="delete book",
            route="book-detail",
            method="delete"
        )
        view_top_rated_books_perm, _ = Permission.objects.get_or_create(
            name="view top rated books",
            route="book-top-rated",
            method="get"
        )

        # ----- 借阅记录权限 -----
        view_borrow_records_perm, _ = Permission.objects.get_or_create(
            name="view borrow record",
            route="borrow-record-list",
            method="get"
        )
        create_borrow_record_perm, _ = Permission.objects.get_or_create(
            name="create borrow record",
            route="borrow-record-list",
            method="post"
        )
        view_borrow_record_detail_perm, _ = Permission.objects.get_or_create(
            name="view borrow record detail",
            route="borrow-record-detail",
            method="get"
        )
        update_borrow_record_perm, _ = Permission.objects.get_or_create(
            name="update borrow record",
            route="borrow-record-detail",
            method="put"
        )
        patch_borrow_record_perm, _ = Permission.objects.get_or_create(
            name="update borrow record",
            route="borrow-record-detail",
            method="patch"
        )
        delete_borrow_record_perm, _ = Permission.objects.get_or_create(
            name="delete borrow record",
            route="borrow-record-detail",
            method="delete"
        )
        check_book_status_perm, _ = Permission.objects.get_or_create(
            name="check book borrow status",
            route="borrow-record-check-book-status",
            method="get"
        )
        pending_approvals_perm, _ = Permission.objects.get_or_create(
            name="view pending borrow approvals",
            route="borrow-record-pending-approvals",
            method="get"
        )
        approve_borrow_perm, _ = Permission.objects.get_or_create(
            name="approve borrow request",
            route="borrow-record-approve",
            method="post"
        )
        return_book_perm, _ = Permission.objects.get_or_create(
            name="confirm return book",
            route="borrow-record-return",
            method="post"
        )

        # ----- 推荐权限 -----
        view_recommendations_perm, _ = Permission.objects.get_or_create(
            name="view recommendations",
            route="recommendation-list",
            method="get"
        )
        view_popular_analysis_perm, _ = Permission.objects.get_or_create(
            name="view popular analysis",
            route="recommendation-popular_books_analysis",
            method="get"
        )
        view_predictive_analysis_perm, _ = Permission.objects.get_or_create(
            name="view predictive analysis",
            route="recommendation-predictive_analysis",
            method="get"
        )

        # ----- 分类权限 -----
        view_categories_perm, _ = Permission.objects.get_or_create(
            name="view category",
            route="category-list",
            method="get"
        )
        create_category_perm, _ = Permission.objects.get_or_create(
            name="create category",
            route="category-list",
            method="post"
        )
        view_category_detail_perm, _ = Permission.objects.get_or_create(
            name="view category detail",
            route="category-detail",
            method="get"
        )
        update_category_perm, _ = Permission.objects.get_or_create(
            name="update category",
            route="category-detail",
            method="put"
        )
        patch_category_perm, _ = Permission.objects.get_or_create(
            name="update category",
            route="category-detail",
            method="patch"
        )
        delete_category_perm, _ = Permission.objects.get_or_create(
            name="delete category",
            route="category-detail",
            method="delete"
        )

        # ----- 作者权限 -----
        view_authors_perm, _ = Permission.objects.get_or_create(
            name="view author",
            route="author-list",
            method="get"
        )
        create_author_perm, _ = Permission.objects.get_or_create(
            name="create author",
            route="author-list",
            method="post"
        )
        view_author_detail_perm, _ = Permission.objects.get_or_create(
            name="view author detail",
            route="author-detail",
            method="get"
        )
        update_author_perm, _ = Permission.objects.get_or_create(
            name="update author",
            route="author-detail",
            method="put"
        )
        patch_author_perm, _ = Permission.objects.get_or_create(
            name="update author",
            route="author-detail",
            method="patch"
        )
        delete_author_perm, _ = Permission.objects.get_or_create(
            name="delete author",
            route="author-detail",
            method="delete"
        )

        # ----- 用户权限 -----
        view_users_perm, _ = Permission.objects.get_or_create(
            name="view user",
            route="user-list",
            method="get"
        )
        create_user_perm, _ = Permission.objects.get_or_create(
            name="create user",
            route="user-list",
            method="post"
        )
        view_user_detail_perm, _ = Permission.objects.get_or_create(
            name="view user detail",
            route="user-detail",
            method="get"
        )
        update_user_perm, _ = Permission.objects.get_or_create(
            name="update user",
            route="user-detail",
            method="put"
        )
        patch_user_perm, _ = Permission.objects.get_or_create(
            name="update user",
            route="user-detail",
            method="patch"
        )
        delete_user_perm, _ = Permission.objects.get_or_create(
            name="delete user",
            route="user-detail",
            method="delete"
        )
        view_user_types_perm, _ = Permission.objects.get_or_create(
           name="view user types",
            route="user-user-types",
            method="get"
        )

        # ----- assign permissions to roles -----

        # reader permissions
        reader_permissions = [
            login_perm,
            view_announcement_perm,
            view_announcement_detail_perm,
            view_books_perm,
            view_book_detail_perm,
            view_top_rated_books_perm,
            view_borrow_records_perm,  # 只能看到自己的记录（通过视图过滤）
            create_borrow_record_perm,
            view_borrow_record_detail_perm,
            update_borrow_record_perm,  # 用于提交还书申请
            check_book_status_perm,
            return_book_perm,
            view_recommendations_perm,
            view_categories_perm,
            view_category_detail_perm,
            view_authors_perm,
            view_author_detail_perm,
        ]
        reader_role.permissions.add(*reader_permissions)

        # librarian permissions
        librarian_permissions = [
            login_perm,
            view_announcement_perm,
            view_announcement_detail_perm,
            create_announcement_perm,
            update_announcement_perm,
            patch_announcement_perm,
            delete_announcement_perm,
            toggle_announcement_perm,
            view_books_perm,
            view_book_detail_perm,
            create_book_perm,
            update_book_perm,
            patch_book_perm,
            delete_book_perm,
            view_borrow_records_perm,
            view_borrow_record_detail_perm,
            pending_approvals_perm,
            approve_borrow_perm,
            check_book_status_perm,
            view_categories_perm,
            view_category_detail_perm,
            create_category_perm,
            update_category_perm,
            patch_category_perm,
            delete_category_perm,
            view_authors_perm,
            view_author_detail_perm,
            create_author_perm,
            update_author_perm,
            patch_author_perm,
            delete_author_perm,
        ]
        librarian_role.permissions.add(*librarian_permissions)

        # system admin permissions (all permissions)
        all_permissions = Permission.objects.all()
        admin_role.permissions.add(*all_permissions)

        # update existing user roles
        for user in User.objects.all():
            # clear existing roles
            user.roles.clear()
            
            # assign roles based on user type
            if user.user_type == '0':  # reader
                user.roles.add(reader_role)
            elif user.user_type == '1':  # librarian
                user.roles.add(librarian_role)
            elif user.user_type == '2':  # system admin
                user.roles.add(admin_role)
            
            # super users also have admin role
            if user.is_super:
                user.roles.add(admin_role)

            self.stdout.write(self.style.SUCCESS('success')) 