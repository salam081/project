from django.shortcuts import render
from django.http import HttpResponseForbidden,HttpResponse
from functools import wraps
def group_required(required_groups):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # 1. Block if not logged in
            if not request.user.is_authenticated:
                return render(request, "accounts/login.html")
            
            # 2. Get the user group
            user_group = request.user.group 
            
            # 3. Allow only if the group title is in the required groups
            if user_group and user_group.title in required_groups:
                return view_func(request, *args, **kwargs)
            
            # 4. Otherwise, show login page
            return render(request, "accounts/login.html")
        return wrapped_view
    return decorator
