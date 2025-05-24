from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/users/', views.UserView.as_view(), name='user_list'),
    path('api/users/<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),
    path('api/users/current/', views.UserCurrentView.as_view(), name='current_user'),
    path('api/users/logout/', views.LogoutView.as_view(), name='logout'),
    path('api/users/chatted/', views.UserChattedView.as_view(), name='chatted_users'),
    path('api/messages/', views.MessageView.as_view(), name='message_list'),
    path('api/messages/<int:pk>/', views.MessageDetailView.as_view(), name='message_detail'),
    path('api/messages/seen/', views.MessageSeenView.as_view(), name='message_seen'),
    path('api/groups/', views.GroupView.as_view(), name='group_list'),
    path('api/groups/<int:pk>/', views.GroupDetailView.as_view(), name='group_detail'),
    path('api/groups/join/', views.GroupJoinView.as_view(), name='group_join'),
    path('api/groups/search/', views.GroupSearchView.as_view(), name='group_search'),
    path('api/upload/', views.UploadView.as_view(), name='file_upload'),
]