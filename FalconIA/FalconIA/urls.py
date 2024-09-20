"""
URL configuration for FalconIA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
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
# mi_proyecto/urls.py
from django.contrib import admin
from django.urls import path, include
from IA import views as ia_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('signup/', ia_views.signup, name='signup'),
    path('', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    # path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('logout/', auth_views.LoginView.as_view(template_name='login.html'), name='logout'),
    path('dashboard/', ia_views.dashboard, name='dashboard'),
    path('upload/', ia_views.upload_document, name='upload_document'),

     path('send_message/', ia_views.send_message, name='send_message'),
    path('new_chat/', ia_views.new_chat, name='new_chat'),
    path('delete_chat/<int:chat_id>/', ia_views.delete_chat, name='delete_chat'),
    path('rename_chat/<int:chat_id>/', ia_views.rename_chat, name='rename_chat'),
    path('update_chat_title/<int:chat_id>/', ia_views.update_chat_title, name='update_chat_title'),
]

