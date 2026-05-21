from django.urls import path

from .views import (
    SendOTPView,
    VerifyOTPView,
    ParentRegisterView,

    MeView,
    UpdateLanguageView,
    ParentChildLogoutView,

    CreatePairingCodeView,
    ChildRegisterByCodeView,
    MyChildrenView,

    SendChildLocationView,
    ChildLastLocationView,
    ChildLocationHistoryView,

    DeviceTokenView,
    DeviceLogoutView,

    ParentRouteListCreateView,
    ParentRouteDetailView,
    AssignRouteToChildView,
    ParentChildAssignmentsView,
    ChildActiveRoutesView,
    RouteAlertListView,
)


urlpatterns = [
    # Auth / Register
    path(
        "auth/send-otp/",
        SendOTPView.as_view(),
        name="send-otp",
    ),
    path(
        "auth/verify-otp/",
        VerifyOTPView.as_view(),
        name="verify-otp",
    ),
    path(
        "auth/parent/register/",
        ParentRegisterView.as_view(),
        name="parent-register",
    ),

    # User
    path(
        "me/",
        MeView.as_view(),
        name="me",
    ),
    path(
        "me/language/",
        UpdateLanguageView.as_view(),
        name="update-language",
    ),

    # Parent / Child pairing
    path(
        "parent/pairing-code/",
        CreatePairingCodeView.as_view(),
        name="create-pairing-code",
    ),
    path(
        "parent/children/",
        MyChildrenView.as_view(),
        name="my-children",
    ),
    path(
        "child/register-by-code/",
        ChildRegisterByCodeView.as_view(),
        name="child-register-by-code",
    ),
    path(
    "parent/children/<int:child_id>/logout/",
    ParentChildLogoutView.as_view(),
    name="parent-child-logout",
    ),

    # Location
    path(
        "child/location/",
        SendChildLocationView.as_view(),
        name="send-child-location",
    ),
    path(
        "parent/children/<int:child_id>/last-location/",
        ChildLastLocationView.as_view(),
        name="child-last-location",
    ),
    path(
        "parent/children/<int:child_id>/location-history/",
        ChildLocationHistoryView.as_view(),
        name="child-location-history",
    ),

    # Device / Firebase token
    path(
        "device-token/",
        DeviceTokenView.as_view(),
        name="device-token",
    ),
    path(
        "device-token/logout/",
        DeviceLogoutView.as_view(),
        name="device-token-logout",
    ),

    # Routes
    path(
        "parent/routes/",
        ParentRouteListCreateView.as_view(),
        name="parent-routes",
    ),
    path(
        "parent/routes/<int:route_id>/",
        ParentRouteDetailView.as_view(),
        name="parent-route-detail",
    ),
    path(
        "parent/routes/assign/",
        AssignRouteToChildView.as_view(),
        name="assign-route-to-child",
    ),
    path(
        "parent/children/<int:child_id>/routes/",
        ParentChildAssignmentsView.as_view(),
        name="parent-child-routes",
    ),
    path(
        "child/routes/active/",
        ChildActiveRoutesView.as_view(),
        name="child-active-routes",
    ),

    # Route alerts
    path(
        "parent/route-alerts/",
        RouteAlertListView.as_view(),
        name="route-alerts",
    ),
]