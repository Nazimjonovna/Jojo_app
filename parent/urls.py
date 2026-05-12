from django.urls import path

from .views import (
    SendChildLocationView,
    ChildLastLocationView,
    DeviceTokenView,
    SendOTPView,
    VerifyOTPView,
    ParentRegisterView,
    ParentLoginView,
    CreatePairingCodeView,
    ChildRegisterByCodeView,
    MyChildrenView,
    ParentRouteListCreateView,
    ParentRouteDetailView,
    AssignRouteToChildView,
    ParentChildAssignmentsView,
    ChildActiveRoutesView,
    RouteAlertListView,
)


urlpatterns = [
    path("auth/send-otp/", SendOTPView.as_view()),
    path("auth/verify-otp/", VerifyOTPView.as_view()),
    path("auth/parent/register/", ParentRegisterView.as_view()),
    path("auth/parent/login/", ParentLoginView.as_view()),
    path("parent/pairing-code/", CreatePairingCodeView.as_view()),
    path("child/register-by-code/", ChildRegisterByCodeView.as_view()),
    path("parent/children/", MyChildrenView.as_view()),
    # Location
    path(
        "child/location/",
        SendChildLocationView.as_view(),
        name="send-child-location"
    ),
    path(
        "parent/children/<int:child_id>/last-location/",
        ChildLastLocationView.as_view(),
        name="child-last-location"
    ),

    # Routes
    path(
        "parent/routes/",
        ParentRouteListCreateView.as_view(),
        name="parent-routes"
    ),
    path(
        "parent/routes/<int:route_id>/",
        ParentRouteDetailView.as_view(),
        name="parent-route-detail"
    ),
    path(
        "parent/routes/assign/",
        AssignRouteToChildView.as_view(),
        name="assign-route-to-child"
    ),
    path(
        "parent/children/<int:child_id>/routes/",
        ParentChildAssignmentsView.as_view(),
        name="parent-child-routes"
    ),
    path(
        "child/routes/active/",
        ChildActiveRoutesView.as_view(),
        name="child-active-routes"
    ),

    # Alerts
    path(
        "parent/route-alerts/",
        RouteAlertListView.as_view(),
        name="route-alerts"
    ),

    # Firebase token
    path(
        "device-token/",
        DeviceTokenView.as_view(),
        name="device-token"
    ),
]