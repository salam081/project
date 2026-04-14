


from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from .models import UserActivity


class ActivityLogMiddleware(MiddlewareMixin):
    # def process_request(self, request):
    #     # Skip login/logout/admin/static/media pages to avoid redirect loops
    #     exempt_paths = (
    #         '/login',
    #         '/logout',
    #         '/admin',
    #         '/static',
    #         '/media',
    #         '/home'
    #     )

    #     # Redirect to login if session expired, but skip exempt paths
    #     if not request.user.is_authenticated and not any(request.path.startswith(p) for p in exempt_paths):
    #         messages.warning(request, "Your session has expired. Login.")
    #         return redirect('login')


    def process_response(self, request, response):
        # ✅ Log user actions only for authenticated users (non-admin/static)
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
        """Helper to safely get client IP."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')



