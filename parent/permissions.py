from rest_framework.permissions import BasePermission

from .models import User, ParentChild


class IsParent(BasePermission):
    message = "Faqat parent ruxsat oladi."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_PARENT
        )


class IsChild(BasePermission):
    message = "Faqat child ruxsat oladi."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.ROLE_CHILD
        )


class IsParentOfChild(BasePermission):
    message = "Bu child sizga tegishli emas."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role != User.ROLE_PARENT:
            return False

        child_id = view.kwargs.get("child_id")

        if not child_id:
            return False

        return ParentChild.objects.filter(
            parent=request.user,
            child_id=child_id
        ).exists()