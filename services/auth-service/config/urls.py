from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health_check(request):
    return JsonResponse({'status': 'healthy', 'service': 'auth-service'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
]

