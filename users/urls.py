from django.urls import path
from .views import RegisterView
from .google import GoogleLoginView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('google/', GoogleLoginView.as_view(), name='google_login'),
]