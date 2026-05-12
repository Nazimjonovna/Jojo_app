import re

from django.contrib.auth.hashers import make_password
from rest_framework import serializers

from .models import (
    User,
    PairingCode,
    ChildLocation,
    ChildLastLocation,
    DeviceToken,
    SafeRoute,
    SafeRoutePoint,
    ChildRouteAssignment,
    RouteAlert,
)


PHONE_REGEX = r"^\+998\d{9}$"


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value

    def validate_code(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError(
                "SMS kod 6 xonali raqam bo‘lishi kerak."
            )
        return value


class ParentRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=128
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "password",
            "first_name",
            "last_name",
            "language",
            "avatar",
            'gender',
        ]
        read_only_fields = ["id"]

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Bu telefon raqam bilan foydalanuvchi oldin ro‘yxatdan o‘tgan."
            )
        return value

    def validate_language(self, value):
        allowed_languages = ["uz_latn", "uz_cyrl", "ru", "en"]
        if value not in allowed_languages:
            raise serializers.ValidationError(
                "Til uz_latn, uz_cyrl, ru yoki en bo‘lishi kerak."
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        phone = validated_data.pop("phone")
        user = User.objects.create(
            username=phone,
            phone=phone,
            role=User.ROLE_PARENT,
            **validated_data
        )
        user.set_password(password)
        user.save()
        return user


class ParentLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value


class UpdateLanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(
        choices=["uz_latn", "uz_cyrl", "ru", "en"]
    )


class PairingCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PairingCode
        fields = [
            "id",
            "code",
            "expires_at",
            "is_used",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "expires_at",
            "is_used",
            "created_at",
        ]


class ChildRegisterByCodeSerializer(serializers.Serializer):
    pairing_code = serializers.CharField(max_length=10)
    child_name = serializers.CharField(max_length=150)
    language = serializers.ChoiceField(
        choices=["uz_latn", "uz_cyrl", "ru", "en"],
        default="uz_latn"
    )

    def validate_pairing_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "Pairing code faqat raqamlardan iborat bo‘lishi kerak."
            )

        if len(value) != 6:
            raise serializers.ValidationError(
                "Pairing code 6 xonali bo‘lishi kerak."
            )

        return value

    def validate_child_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Bola ismi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "first_name",
            "last_name",
            "role",
            "language",
            "avatar",
        ]


class ChildLastLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildLastLocation
        fields = [
            "latitude",
            "longitude",
            "accuracy",
            "battery_level",
            "speed",
            "heading",
            "updated_at",
        ]


class ChildSerializer(serializers.ModelSerializer):
    last_location = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "role",
            "language",
            "avatar",
            "last_location",
        ]

    def get_last_location(self, obj):
        try:
            return ChildLastLocationSerializer(obj.last_location).data
        except ChildLastLocation.DoesNotExist:
            return None


class ChildLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChildLocation
        fields = [
            "id",
            "child",
            "latitude",
            "longitude",
            "accuracy",
            "battery_level",
            "speed",
            "heading",
            "source",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "child",
            "source",
            "created_at",
        ]

    def validate_latitude(self, value):
        if value < -90 or value > 90:
            raise serializers.ValidationError(
                "Latitude -90 va 90 orasida bo‘lishi kerak."
            )
        return value

    def validate_longitude(self, value):
        if value < -180 or value > 180:
            raise serializers.ValidationError(
                "Longitude -180 va 180 orasida bo‘lishi kerak."
            )
        return value

    def validate_battery_level(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError(
                "Battery level 0 va 100 orasida bo‘lishi kerak."
            )
        return value


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = [
            "id",
            "token",
            "device_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]


class SafeRoutePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafeRoutePoint
        fields = [
            "id",
            "order",
            "latitude",
            "longitude",
            "title",
        ]

    def validate_latitude(self, value):
        if value < -90 or value > 90:
            raise serializers.ValidationError(
                "Latitude -90 va 90 orasida bo‘lishi kerak."
            )
        return value

    def validate_longitude(self, value):
        if value < -180 or value > 180:
            raise serializers.ValidationError(
                "Longitude -180 va 180 orasida bo‘lishi kerak."
            )
        return value


class SafeRouteSerializer(serializers.ModelSerializer):
    points = SafeRoutePointSerializer(many=True, required=False)

    class Meta:
        model = SafeRoute
        fields = [
            "id",
            "name",
            "description",
            "color",
            "is_active",
            "points",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Route nomi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value

    def validate_points(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                "Marshrut uchun kamida 2 ta nuqta kerak."
            )

        return value

    def create(self, validated_data):
        points_data = validated_data.pop("points", [])

        route = SafeRoute.objects.create(**validated_data)

        for index, point_data in enumerate(points_data):
            SafeRoutePoint.objects.create(
                route=route,
                order=point_data.get("order", index),
                latitude=point_data["latitude"],
                longitude=point_data["longitude"],
                title=point_data.get("title"),
            )

        return route

    def update(self, instance, validated_data):
        points_data = validated_data.pop("points", None)

        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get(
            "description",
            instance.description
        )
        instance.color = validated_data.get("color", instance.color)
        instance.is_active = validated_data.get(
            "is_active",
            instance.is_active
        )
        instance.save()

        if points_data is not None:
            instance.points.all().delete()

            for index, point_data in enumerate(points_data):
                SafeRoutePoint.objects.create(
                    route=instance,
                    order=point_data.get("order", index),
                    latitude=point_data["latitude"],
                    longitude=point_data["longitude"],
                    title=point_data.get("title"),
                )

        return instance


class ChildRouteAssignmentSerializer(serializers.ModelSerializer):
    route = SafeRouteSerializer(read_only=True)

    route_id = serializers.PrimaryKeyRelatedField(
        queryset=SafeRoute.objects.all(),
        source="route",
        write_only=True
    )
    child_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_CHILD),
        source="child",
        write_only=True
    )

    class Meta:
        model = ChildRouteAssignment
        fields = [
            "id",
            "child_id",
            "route_id",
            "route",
            "status",
            "allowed_radius_meters",
            "notify_on_deviation",
            "start_time",
            "end_time",
            "days_of_week",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def validate_allowed_radius_meters(self, value):
        if value < 10:
            raise serializers.ValidationError(
                "Allowed radius kamida 10 metr bo‘lishi kerak."
            )

        if value > 5000:
            raise serializers.ValidationError(
                "Allowed radius 5000 metrdan oshmasligi kerak."
            )

        return value

    def validate_days_of_week(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "days_of_week list bo‘lishi kerak. Masalan: [1, 2, 3, 4, 5]"
            )

        for day in value:
            if day not in [1, 2, 3, 4, 5, 6, 7]:
                raise serializers.ValidationError(
                    "days_of_week ichida faqat 1 dan 7 gacha son bo‘lishi kerak."
                )

        return value

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")

        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError(
                {
                    "end_time": "end_time start_time dan keyin bo‘lishi kerak."
                }
            )

        return attrs


class RouteAlertSerializer(serializers.ModelSerializer):
    child = ChildSerializer(read_only=True)
    route_name = serializers.CharField(
        source="assignment.route.name",
        read_only=True
    )

    class Meta:
        model = RouteAlert
        fields = [
            "id",
            "child",
            "route_name",
            "alert_type",
            "distance_meters",
            "created_at",
        ]
        read_only_fields = fields