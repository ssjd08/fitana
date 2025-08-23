"""
URL configuration for fitana project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from debug_toolbar.toolbar import debug_toolbar_urls
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions


schema_view = get_schema_view(
   openapi.Info(
      title="ّFitana API",
      default_version='v1',
      description="""
        API documentation for Fitana questionnaire system.
        
        ## Authentication
        This API uses JWT (JSON Web Token) for authentication.
        
        ### How to authenticate:
        1. POST to `/auth/login/` with your credentials to get access and refresh tokens
        2. Copy the access token from the response
        3. Click the "Authorize" button below
        4. Enter: `Bearer <your-access-token>`
        5. Click "Authorize"
        
        ### Token endpoints:
        - `/auth/login/` - Get access and refresh tokens
        - `/auth/token/refresh/` - Refresh your access token
        - `/auth/logout/` - Logout (if implemented)
        """,
      terms_of_service="https://www.google.com/policies/terms/",
      contact=openapi.Contact(email="contact@snippets.local"),
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('admin/', admin.site.urls),
    path('auth/', include('accounts.urls')),
    path('questionnaire/', include('questionnaire.urls')),
    path('payment/', include('payment.urls')),
    
    # Swagger URLs
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', 
            schema_view.without_ui(cache_timeout=0), 
            name='schema-json'),
    re_path(r'^swagger/$', 
            schema_view.with_ui('swagger', cache_timeout=0), 
            name='schema-swagger-ui'),
    re_path(r'^redoc/$', 
            schema_view.with_ui('redoc', cache_timeout=0), 
            name='schema-redoc'),
    
    
] + debug_toolbar_urls()
