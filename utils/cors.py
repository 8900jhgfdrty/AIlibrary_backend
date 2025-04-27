from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse


class CorsMiddleware(MiddlewareMixin):
    """解决前后端的跨域问题
    """

    def process_request(self, request):
        """处理OPTIONS预检请求"""
        if request.method == 'OPTIONS':
            response = HttpResponse()
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Type'
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
            response['Access-Control-Max-Age'] = '3600'  # 预检请求缓存时间
            return response
        return None

    def process_response(self, request, response):
        """为所有响应添加CORS头"""
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-User-Type'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        return response
