from rest_framework.permissions import BasePermission
from api import models
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
import logging
from rest_framework import permissions
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger('permissions')

class RbacPermission(BasePermission):
    """     """
    message = _("You do not have permission to perform this action")

    def has_permission(self, request, view):
        """检查是否有权限访问当前接口"""
        # 1. get current route information
        router_name = request.resolver_match.view_name
        method = request.method.lower()

        # record access information (for debugging)
        logger.debug(f"访问: {router_name} - {method} - 用户: {request.user.id if hasattr(request.user, 'id') else '匿名'}")

        # for whitelist views and OPTIONS requests, directly pass
        if method == 'options':
            return True
            
        # for safe methods (GET, HEAD, OPTIONS), directly pass
        if method in ['get', 'head', 'post', 'options']:
            return True

        # if there is no authenticated user, reject access
        if not hasattr(request.user, 'id'):
            return False

        # 2. super admin has all permissions
        if hasattr(request.user, 'is_super') and request.user.is_super:
            return True
            
        # 3. check user type, librarians and system admins have modification permissions
        if hasattr(request.user, 'user_type'):
            # check various possible forms of user_type (string or number)
            user_type = request.user.user_type
            if user_type == 1 or user_type == 2 or user_type == '1' or user_type == '2':
                return True
                
        # for PUT/PATCH/DELETE requests, need to check if there is admin permission
        if method in ['put', 'patch', 'delete'] and view.__class__.__name__ in ['BookViewSet', 'AuthorViewSet', 'CategoryViewSet', 'AnnouncementViewSet']:
            return False
            
        # normal users cannot perform modification operations
        return False

    def has_object_permission(self, request, view, obj):
        """object-level permission check"""
        # if super admin, has all permissions
        if hasattr(request.user, 'is_super') and request.user.is_super:
            return True
            
        # if safe method (GET, HEAD, etc.), directly pass
        if request.method.lower() in ['get', 'head', 'options']:
            return True
            
        # check user type, librarians and system admins have modification permissions
        if hasattr(request.user, 'user_type'):
            user_type = request.user.user_type
            # librarian (1) or system admin (2) has modification permissions for books, authors, categories
            if user_type == 1 or user_type == 2 or user_type == '1' or user_type == '2':
                # allow admin to modify books, authors, categories and announcements
                if isinstance(obj, (models.Book, models.Author, models.Category, models.Announcement)):
                    return True
        
        # borrowing record object-level permission: normal users can only view/modify their borrowing records
        if hasattr(obj, 'user') and isinstance(obj, models.BorrowRecord):
            # if the record owner, allow access
            if obj.user.id == request.user.id:
                return True
                
            # if the user is a librarian or system admin, allow access
            if hasattr(request.user, 'user_type'):
                user_type = request.user.user_type
                if user_type == 1 or user_type == 2 or user_type == '1' or user_type == '2':
                    return True
            
            return False
        
        # check for announcements:
        if isinstance(obj, models.Announcement):
            # if the announcement is visible, everyone can see it
            if obj.is_visible:
                return True
                
            # invisible announcements can only be seen by admins
            if hasattr(request.user, 'user_type'):
                user_type = request.user.user_type
                if user_type == 1 or user_type == 2 or user_type == '1' or user_type == '2':
                    return True
                
            return False
        
        # for other types of objects, non-admins are not allowed to modify
        return False

class BaseRolePermission(permissions.BasePermission):
    """
    base role permission class, providing common role check methods
    """
    def has_role(self, user, role_type):
        """
        check if the user has the specified role
        
        Args:
            user: user object
            role_type: role type (0: reader, 1: librarian, 2: system admin)
            
        Returns:
            bool: whether the user has the specified role
        """
        # check user type
        if hasattr(user, 'user_type'):
            if str(user.user_type) == str(role_type) or user.user_type == role_type:
                return True
                
        # check user roles
        try:
            if hasattr(user, 'roles'):
                role_map = {
                    0: ['Reader'],
                    1: ['Librarian'],
                    2: ['System Administrator', 'System Admin']
                }
                role_names = role_map.get(role_type, [])
                user_roles = [role.name if hasattr(role, 'name') else str(role) for role in user.roles.all()]
                if any(role in role_names for role in user_roles):
                    return True
        except (ObjectDoesNotExist, AttributeError):
            pass
            
        # for system admin, check superuser status
        if role_type == 2 and getattr(user, 'is_superuser', False):
            return True
            
        return False

class IsLibrarian(BaseRolePermission):
    """
    check if the user is a librarian
    """
    message = 'Only librarians can perform this action'
    
    def has_permission(self, request, view):
        return bool(request.user and self.has_role(request.user, 1))

class IsSystemAdmin(BaseRolePermission):
    """
    check if the user is a system admin
    """
    message = 'Only system admins can perform this action'
    
    def has_permission(self, request, view):
        return bool(request.user and self.has_role(request.user, 2))

class IsLibrarianOrSystemAdmin(BaseRolePermission):
    """
    check if the user is a librarian or system admin
    """
    message = 'Only librarians or system admins can perform this action'
    
    def has_permission(self, request, view):
        return bool(
            request.user and 
            (self.has_role(request.user, 1) or self.has_role(request.user, 2))
        )

class IsReader(BaseRolePermission):
    """
    check if the user is a reader
    """
    message = 'Only readers can perform this action'
    
    def has_permission(self, request, view):
        # 所有登录用户默认都具有读者权限
        return bool(request.user and request.user.is_authenticated)

class IsSelfOrAdmin(BaseRolePermission):
    """
    check if the user is himself or admin
    used to ensure that users can only access/modify their own data, unless they are admins
    """
    message = 'You can only access or modify your own data'
    
    def has_object_permission(self, request, view, obj):
        # check if the user is an admin
        is_admin = self.has_role(request.user, 1) or self.has_role(request.user, 2)
        if is_admin:
            return True
            
        # check if the user is himself
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'id'):
            return obj.id == request.user.id
            
        return False

