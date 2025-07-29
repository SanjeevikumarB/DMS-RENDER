from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/files/', include('files.urls')),
    path('api/files/sharing/', include('sharing.urls')),
    path('api/accounts/', include('accounts.urls')),
]
