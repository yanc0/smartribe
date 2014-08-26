from rest_framework.permissions import BasePermission

from api.authenticate import AuthUser
from core.models import Offer


class IsConcernedByMeeting(BasePermission):
    """

    """
    def has_permission(self, request, view):
        user, response = AuthUser().authenticate(request)
        data = request.DATA
        if not user:
            return False
        if 'offer' not in data:
            return False
        if not Offer.objects.filter(id=data['offer']).exists():
            return False
        of = Offer.objects.get(id=data['offer'])
        if user is not of.user and user is not of.request.user:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        user, response = AuthUser().authenticate(request)
        if not user:
            return False
        if user is not obj.user and user is not obj.request.user:
            return False
        return True