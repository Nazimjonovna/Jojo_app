from rest_framework import serializers
from .models import User, Validatedcode

class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=255)

    def validate_phone(self, value):
        if not value.startswith('+998'):
            raise serializers.ValidationError("Phone number must start with +998")
        return value
    
    
class SMSCodeSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=255)

    def validate_phone(self, value):
        if not value.startswith('+998'):
            raise serializers.ValidationError("Phone number must start with +998")
        return value
    
class Validateser(serializers.ModelSerializer):

    class Meta:
        model = Validatedcode
        fields = ('phone', 'code')

class Userserializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'


class UserLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('phone', 'password')