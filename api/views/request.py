from django.contrib.admin.models import CHANGE
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.decorators import link, action
from rest_framework.response import Response
from rest_framework import status

from api.permissions.common import IsJWTAuthenticated, IsJWTOwner
from api.serializers import RequestSerializer, RequestCreateSerializer
from api.views.abstract_viewsets.custom_viewset import CustomViewSet
from core.models import Request, Member, Skill, Offer, Community


class RequestViewSet(CustomViewSet):
    """

    Inherits standard characteristics from ModelViewSet:

            | **Endpoint**: /requests/
            | **Methods**: GET / POST / PUT / PATCH / DELETE / OPTIONS
            | **Permissions**:
            |       - Default : IsJWTOwner
            |       - GET : IsJWTAuthenticated
            |       - POST : IsJWTSelf
            | **Notes**:
            |       - GET response restricted to 'Requests' objects linked with user and not closed

    """
    model = Request
    create_serializer_class = RequestCreateSerializer
    serializer_class = RequestSerializer
    filter_fields = ['user__id', 'category__id', 'closed']

    def get_permissions(self):
        if self.request.method in ['GET', 'POST']:
            return [IsJWTAuthenticated()]
        return [IsJWTOwner()]

    def pre_save(self, obj):
        super().pre_save(obj)
        self.set_auto_user(obj)

    def get_queryset(self):
        my_communities = Member.objects.filter(user=self.request.user, status="1").values('community')
        linked_users = Member.objects.filter(community__in=my_communities).values('user')
        return self.model.objects.filter(Q(user__in=linked_users),
                                         Q(community=None) | Q(community__in=my_communities))

    @link()
    def list_my_requests(self, request, pk=None):
        """
        List the requests created by the authenticated user.

                | **permission**: JWTAuthenticated
                | **endpoint**: /requests/0/list_my_requests/
                | **method**: GET
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - List of request objects :
                |           - user (integer)
                |           - community (Community / Optional)
                |           - category (integer)
                |           - title (char 50)
                |           - detail (text)
                |           - creation_date (datetime)
                |           - expected_end_date (datetime)
                |           - end_date (datetime)
                |           - auto_close (boolean)
                |           - closed (boolean)
                | **other actions**:
                |       None

        """
        requests = self.model.objects.filter(user=self.request.user).order_by('-created_on')
        serializer = self.get_paginated_serializer(requests)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @link()
    def list_community_requests(self, request, pk=None):
        """ """
        if not 'community' in request.QUERY_PARAMS:
            return Response({'detail': 'Missing community index.'}, status=status.HTTP_400_BAD_REQUEST)
        if not Community.objects.filter(id=request.QUERY_PARAMS['community']).exists():
            return Response({'detail': 'This community does not exist'}, status=status.HTTP_400_BAD_REQUEST)
        community = Community.objects.get(id=request.QUERY_PARAMS['community'])
        members = Member.objects.filter(community=community, status='1').values('user')
        users = get_user_model().objects.filter(id__in=members)
        requests = self.get_queryset().filter(Q(community=community)
                                              | (Q(community=None) & Q(user__in=users)))
        serializer = self.get_paginated_serializer(requests.order_by('-created_on'))
        return Response(serializer.data, status=status.HTTP_200_OK)

    @link()
    def list_suggested_requests_skills(self, request, pk=None):
        """  """
        user = self.request.user
        my_category_list = Skill.objects.filter(user=user).values('category').distinct()

        queryset = self.get_queryset().exclude(user=user).filter(category__in=my_category_list).order_by('-created_on')
        serializer = self.get_paginated_serializer(queryset)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @link()
    def get_offer_count(self, request, pk=None):
        """  """
        req, response = self.validate_object(request, pk)
        if not req:
            return response
        count = Offer.objects.filter(request=req).count()
        return Response({'count': count}, status=status.HTTP_200_OK)

    @action()
    def close_request(self, request, pk=None):
        """
        Close a request.

                | **permission**: IsJWTOwner
                | **endpoint**: /requests/{id}/close_request/
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - Modified request object
                | **other actions**:
                |       None

        """
        req, response = self.validate_object(request, pk)
        if not req:
            return response
        if req.user != self.request.user:
            return Response({'detail': 'Operation not allowed.'}, status.HTTP_403_FORBIDDEN)
        req.closed = True
        req.save()
        offers = Offer.objects.filter(request=req, closed=False)
        for offer in offers:
            offer.closed = True
            offer.save()
        serializer = RequestSerializer(req)
        self.log(req, CHANGE, None, "Request closed")
        return Response(serializer.data, status=status.HTTP_200_OK)
