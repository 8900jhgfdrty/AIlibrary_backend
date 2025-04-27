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
    if isinstance(exc, ValidationError):
        # Form validation error
        exc.ret_code = 2001
        exc.status_code = status.HTTP_200_OK
    elif isinstance(exc, AuthenticationFailed):
        # Authentication failed
        exc.ret_code = 2002
        exc.status_code = status.HTTP_200_OK
    elif isinstance(exc, PermissionDenied):
        # No permission to access
        exc.ret_code = 2003
        exc.status_code = status.HTTP_200_OK
    elif isinstance(exc, Http404):
        exc.ret_code = 3001
        exc.status_code = status.HTTP_200_OK

    if isinstance(exc, APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        exc_code = getattr(exc, 'ret_code', -1)
        data = {'code': exc_code, 'detail': exc.detail}

        set_rollback()
        return Response(data, status=exc.status_code, headers=headers)

    # For uncaught exceptions
    data = {'code': -1, 'detail': str(exc)}
    return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BaseViewMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # If this is an exception response, return it directly
        if response.exception:
            return response
        response.data = {"code": 0, "data": response.data}
        response.status_code = status.HTTP_200_OK
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