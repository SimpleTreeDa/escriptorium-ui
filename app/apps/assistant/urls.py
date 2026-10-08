from django.urls import path

from assistant.views import AssistantPage

urlpatterns = [
    path('assistant/', AssistantPage.as_view(), name='assistant'),
]
