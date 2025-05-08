import re

from django.http import Http404
from rest_framework.views import set_rollback, APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, AuthenticationFailed, PermissionDenied
from rest_framework.exceptions import APIException
from rest_framework.viewsets import ModelViewSet
from rest_framework import status
from utils.permissions import RbacPermission


def handle_exception(exc, context):
    """
    全局异常处理函数，转换各类异常为标准API响应格式
    """
    if isinstance(exc, ValidationError):
        # 表单验证错误
        exc.ret_code = 2001
        # 错误码保持400
    elif isinstance(exc, AuthenticationFailed):
        # 身份验证失败
        exc.ret_code = 2002
        # 错误码保持401
    elif isinstance(exc, PermissionDenied):
        # 无权限访问
        exc.ret_code = 2003
        # 错误码保持403
    elif isinstance(exc, Http404):
        # 如果是路径参数问题，提供更友好的错误信息
        request = context.get('request')
        view = context.get('view')
        
        if request and view and hasattr(view, 'basename'):
            resource_name = view.basename.replace('-', ' ').title()
            resource_id = request.parser_context.get('kwargs', {}).get('pk', 'unknown')
            detail = f"{resource_name} with ID {resource_id} does not exist"
        else:
            detail = "Resource not found"
            
        exc.ret_code = 3001
        exc.detail = detail
        # 错误码保持404

    if isinstance(exc, APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        exc_code = getattr(exc, 'ret_code', -1)
        
        # 确保错误响应格式一致
        if isinstance(exc.detail, dict) and 'errors' not in exc.detail:
            data = {'code': exc_code, 'success': False, 'message': "Request validation failed", 'errors': exc.detail}
        else:
            data = {'code': exc_code, 'success': False, 'message': str(exc.detail) if isinstance(exc.detail, str) else "Request failed", 'errors': {'detail': exc.detail} if not isinstance(exc.detail, dict) else exc.detail}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    # 处理未捕获的异常
    data = {'code': -1, 'success': False, 'message': "An unexpected error occurred", 'errors': {'detail': str(exc)}}
    return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BaseViewMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # If this is an exception response, return it directly
        if response.exception:
            return response
            
        # 包装数据，为非200状态码添加错误代码
        if response.status_code >= 400:
            # 对于错误响应，使用非零错误码
            error_code = response.status_code  # 使用HTTP状态码作为错误码
            response.data = {"code": error_code, "data": response.data}
        else:
            # 对于成功响应，使用0作为成功码
            response.data = {"code": 0, "data": response.data}
        
        # 保留原始状态码，不再统一设为200
        # response.status_code = status.HTTP_200_OK
        return response


class PermissionCheckerMixin:
    """Mixin class that provides permission checking functionality"""
    
    def is_admin(self, request=None):
        """Check if user is a system administrator"""
        request = request or self.request
        if not hasattr(request, 'user'):
            return False
        
        # Super administrator
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return True
        
        # System administrator role
        if hasattr(request.user, 'roles') and 'system_admin' in request.user.roles:
            return True
            
        # User type is system administrator
        if hasattr(request.user, 'user_type') and request.user.user_type == '2':
            return True
            
        return False
    
    def is_librarian(self, request=None):
        """Check if user is a librarian"""
        request = request or self.request
        
        # Super administrator or system administrator
        if self.is_admin(request):
            return True
            
        if not hasattr(request, 'user'):
            return False
            
        # Librarian role
        if hasattr(request.user, 'roles') and 'librarian' in request.user.roles:
            return True
            
        # User type is librarian
        if hasattr(request.user, 'user_type') and request.user.user_type == '1':
            return True
            
        return False
    
    def is_reader(self, request=None):
        """Check if user is a reader"""
        request = request or self.request
        if not hasattr(request, 'user'):
            return False
            
        # By default all users can be readers
        return True
    
    def is_object_owner(self, obj):
        """Check if current user is the owner of the object"""
        if not hasattr(self.request, 'user'):
            return False
            
        if not hasattr(obj, 'user_id'):
            return False
            
        return obj.user_id == self.request.user.id

class MineModelViewSet(PermissionCheckerMixin, ModelViewSet):
    """Extended ModelViewSet with permission checking functionality"""
    
    # Default to using RBAC permission system
    permission_classes = [RbacPermission]
    
    def filter_queryset_by_role(self, queryset):
        """Filter queryset based on user role"""
        if not hasattr(self.request, 'user') or not hasattr(self.request.user, 'id'):
            return queryset.none()  # Unauthenticated users get empty results
            
        # Administrators can view all
        if self.is_librarian() or self.is_admin():
            return queryset
            
        # Define field name to determine if object belongs to user
        owner_field = getattr(self, 'owner_field', 'user')
        
        # Regular readers can only view their own records
        return queryset.filter(**{f"{owner_field}_id": self.request.user.id})
    
    def create(self, request, *args, **kwargs):
        # Automatically add user ID
        if hasattr(request, 'user') and hasattr(request.user, 'id'):
            owner_field = getattr(self, 'owner_field', 'user')
            if isinstance(request.data, dict) and owner_field not in request.data:
                request.data[owner_field] = request.user.id
                
        return super().create(request, *args, **kwargs)
        

class MineApiViewSet(BaseViewMixin, APIView):
    pass