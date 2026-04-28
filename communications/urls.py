# communications/urls.py
from django.urls import path
from . import views



urlpatterns = [
    path("", views.conversation_list, name="conversation_list"),
    path("create/", views.create_conversation, name="create_conversation"),
    path("convo/<int:pk>/", views.conversation_detail, name="conversation_detail"),
    path("convo/<int:pk>/upload/", views.upload_attachment, name="upload_attachment"),
    path("ajax/conversations/", views.conversation_list_ajax, name="conversation_list_ajax"),
    path('chat/<int:convo_id>/send/', views.send_message, name='send_message'),

   
    path("conversation/<int:conversation_id>/new_messages/", views.fetch_new_messages, name="fetch_new_messages"),
    path('api/unread-count/', views.unread_message_count_api, name='unread_count_api'),
]
