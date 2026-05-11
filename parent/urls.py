from django.urls import path
from .views import (PhoneView, codeView, ValidatedcodeView, RegisterUserView,)    

urlpatterns = [
    path('phone/', PhoneView.as_view(), name='phone'),
    path('code/', codeView.as_view(), name='code'),
    path('validated-code/', ValidatedcodeView.as_view(), name='validated-code'),
    path('register/', RegisterUserView.as_view(), name='register'),
]