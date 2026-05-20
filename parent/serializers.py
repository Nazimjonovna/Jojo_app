import re

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
            raise serializers.ValidationError("SMS kod 6 xonali bo‘lishi kerak.")
        return value


class ParentRegisterSerializer(serializers.ModelSerializer):
    phone = serializers.CharField(max_length=20)

    device_id = serializers.CharField(
        write_only=True,
        max_length=255,
        required=True
    )

    token = serializers.CharField(
        write_only=True,
        required=True
    )

    device_type = serializers.ChoiceField(
        write_only=True,
        choices=["android", "ios"],
        default="android"
    )

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "full_name",
            "gender",
            "language",
            "avatar",
            "device_id",
            "token",
            "device_type",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "phone": {
                "validators": []
            }
        }

    def validate_phone(self, value):
        if not re.match(PHONE_REGEX, value):
            raise serializers.ValidationError(
                "Telefon raqam +998901234567 formatida bo‘lishi kerak."
            )
        return value

    def validate_full_name(self, value):
        if value and len(value.strip()) < 2:
            raise serializers.ValidationError("full_name juda qisqa.")
        return value

    def validate_device_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value

    def create(self, validated_data):
        validated_data.pop("device_id", None)
        validated_data.pop("token", None)
        validated_data.pop("device_type", None)

        phone = validated_data.pop("phone")

        user = User.objects.create_user(
            phone=phone,
            username=phone,
            role=User.ROLE_PARENT,
            **validated_data
        )

        return user


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
            "child_name",
            "child_gender",
            "child_age",
            "child_avatar",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "code",
            "expires_at",
            "is_used",
            "created_at",
        ]


class CreateChildPairingSerializer(serializers.Serializer):
    child_name = serializers.CharField(
        max_length=255,
        required=True
    )

    child_gender = serializers.ChoiceField(
        choices=["male", "female"],
        required=True
    )

    child_age = serializers.IntegerField(
        min_value=1,
        max_value=18,
        required=True
    )

    child_avatar = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_child_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Bola ismi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value


class ChildRegisterByCodeSerializer(serializers.Serializer):
    pairing_code = serializers.CharField(max_length=10)

    device_id = serializers.CharField(max_length=255, required=True)
    token = serializers.CharField(required=True)
    device_type = serializers.ChoiceField(
        choices=["android", "ios"],
        default="android",
    )

    def validate_pairing_code(self, value):
        value = value.strip().upper()
        if len(value) < 4:
            raise serializers.ValidationError("Pairing code noto‘g‘ri.")
        return value

    def validate_device_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "username",
            "full_name",
            "first_name",
            "last_name",
            "role",
            "gender",
            "age",
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
    pending_delete_time_left_seconds = serializers.SerializerMethodField()
    pending_delete_time_left_days = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "phone",
            "username",
            "full_name",
            "first_name",
            "role",
            "gender",
            "age",
            "language",
            "avatar",
            "child_status",
            "pending_delete_at",
            "pending_delete_time_left_seconds",
            "pending_delete_time_left_days",
            "last_location",
        ]

    def get_last_location(self, obj):
        try:
            return ChildLastLocationSerializer(obj.last_location).data
        except ChildLastLocation.DoesNotExist:
            return None

    def get_pending_delete_time_left_seconds(self, obj):
        if obj.role != User.ROLE_CHILD:
            return None

        if obj.child_status != User.CHILD_STATUS_NON_ACTIVE:
            return None

        return obj.pending_delete_time_left_seconds()

    def get_pending_delete_time_left_days(self, obj):
        seconds = self.get_pending_delete_time_left_seconds(obj)

        if seconds is None:
            return None

        return round(seconds / 86400, 2)


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
            raise serializers.ValidationError("Latitude -90 va 90 orasida bo‘lishi kerak.")
        return value

    def validate_longitude(self, value):
        if value < -180 or value > 180:
            raise serializers.ValidationError("Longitude -180 va 180 orasida bo‘lishi kerak.")
        return value

    def validate_battery_level(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Battery level 0 va 100 orasida bo‘lishi kerak.")
        return value


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = [
            "id",
            "device_id",
            "token",
            "device_type",
            "is_active",
            "last_login_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "last_login_at",
            "created_at",
            "updated_at",
        ]

    def validate_device_id(self, value):
        if not value:
            raise serializers.ValidationError("device_id majburiy.")
        return value

    def validate_token(self, value):
        if not value:
            raise serializers.ValidationError("Firebase token majburiy.")
        return value


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
        read_only_fields = ["id", "created_at"]

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
        instance.description = validated_data.get("description", instance.description)
        instance.color = validated_data.get("color", instance.color)
        instance.is_active = validated_data.get("is_active", instance.is_active)
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
        write_only=True,
    )

    child_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.ROLE_CHILD),
        source="child",
        write_only=True,
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
        read_only_fields = ["id", "created_at"]


class RouteAlertSerializer(serializers.ModelSerializer):
    child = ChildSerializer(read_only=True)
    route_name = serializers.CharField(
        source="assignment.route.name",
        read_only=True,
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


class CreateChildPairingSerializer(serializers.Serializer):
    child_name = serializers.CharField(
        max_length=255,
        required=True
    )

    child_gender = serializers.ChoiceField(
        choices=["male", "female"],
        required=True
    )

    child_age = serializers.IntegerField(
        min_value=1,
        max_value=18,
        required=True
    )

    child_avatar = serializers.ImageField(
        required=False,
        allow_null=True
    )

    def validate_child_name(self, value):
        value = value.strip()

        if len(value) < 2:
            raise serializers.ValidationError(
                "Bola ismi kamida 2 ta belgidan iborat bo‘lishi kerak."
            )

        return value

    def validate_child_age(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Bola yoshi kamida 1 bo‘lishi kerak."
            )

        if value > 18:
            raise serializers.ValidationError(
                "Bola yoshi 18 dan katta bo‘lmasligi kerak."
            )

        return value