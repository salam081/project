from django.utils.deprecation import MiddlewareMixin
from .models import UserActivity
class ActivityLogMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        from .models import UserActivity  # import inside the method

        if (
            request.user.is_authenticated
            and not request.path.startswith('/admin')
            and not request.path.startswith('/static')
        ):
            try:
                UserActivity.objects.create(
                    user=request.user,
                    action=f"Visited {request.path}",
                    path=request.path,
                    method=request.method,
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except Exception:
                pass
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')
