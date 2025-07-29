from django.urls import path
from sharing.views.Share import ShareFileOrFolderAPIView
from sharing.views.SharedWithMe import SharedWithMeAPIView

urlpatterns = [
    path('share/', ShareFileOrFolderAPIView.as_view(), name='share-file-folder'),
    path('shared-with-me/', SharedWithMeAPIView.as_view(), name='shared-with-me'),
]
