from django.contrib.admin.models import ADDITION, DELETION, CHANGE
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action, link
from rest_framework.response import Response

from api.permissions.common import IsJWTAuthenticated
from api.permissions.community import IsCommunityOwner, IsCommunityModerator
from api.serializers import MemberSerializer, MyMembersSerializer, ListCommunityMembersSerializer
from api.serializers.location import LocationSerializer, LocationCreateSerializer
from api.utils.asyncronous_mail import send_mail
from api.utils.notifier import Notifier
from api.views.abstract_viewsets.custom_viewset import CustomViewSet
from core.models import Community, Member, Location, Offer
from api.serializers import CommunitySerializer


class CommunityViewSet(CustomViewSet):
    """
    Inherits standard characteristics from ModelViewSet:

            | **Endpoint**: /communities/
            | **Methods**: GET / POST / PUT / PATCH / DELETE / OPTIONS
            | **Permissions**:
            |       - Default : IsCommunityOwner
            |       - GET or POST: IsJWTAuthenticated
            |       - PUT or PATCH : IsCommunityModerator
            | **Extra-methods:** (HTTP method / permission)
            |       - Memberships management
            |           - join_community (POST / Authenticated)
            |           - list_my_memberships (GET / Authenticated)
            |           - leave_community (POST / Authenticated)
            |           - am_i_member (POST / Authenticated)
            |           - retrieve_members (GET / Moderator)
            |           - accept_member (POST / Moderator)
            |           - ban_member (POST / Moderator)
            |           - promote_moderator (POST / Owner)
            |       - Locations management
            |           - add_location (POST / Member)
            |           - list_locations (GET / Member)
            |           - search_locations (GET / Member)
            |           - delete_location (POST / Moderator)

    """
    model = Community
    serializer_class = CommunitySerializer
    filter_fields = ('name', 'description')
    search_fields = ('name', 'description')

    def get_permissions(self):
        """
        An authenticated user can create a new community or see existing communities.
        Only owner or moderator can modify an existing community.
        """
        if self.request.method == 'DELETE':
            return [IsCommunityOwner()]
        elif self.request.method == 'PUT' or self.request.method == 'PATCH':
            return [IsCommunityModerator()]
        else:
            return [IsJWTAuthenticated()]

    def get_serializer_class(self):
        return self.serializer_class

    def post_save(self, obj, created=False):
        super().post_save(obj, created)
        if self.request.method == 'POST':
            # Creates a member for user, as community owner
            owner = Member.objects.create(user=self.request.user, community=obj, role="0", status="1")

    def get_queryset(self):
        return self.model.objects.all().order_by('name')

    @link(permission_classes=[IsJWTAuthenticated])
    def get_members_count(self, request, pk=None):
        """
        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        count = Member.objects.filter(community=community).count()
        return Response({'count': count}, status=status.HTTP_200_OK)

    # Members management

    ## Simple user actions

    @action(methods=['POST', ], permission_classes=[IsJWTAuthenticated()])
    def join_community(self, request, pk=None):
        """
        Become a new member of a community.

                | **permission**: JWTAuthenticated
                | **endpoint**: /communities/{id}/join_community/
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 201 Created
                |       - 401 Unauthorized
                | **data return**:
                |       None
                | **other actions**:
                |       None

        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        user = self.request.user
        # Check if member already exists
        if Member.objects.filter(user=user, community=community).exists():
            member = Member.objects.get(user=user, community=community)
            return Response(MemberSerializer(member).data, status=status.HTTP_200_OK)
        # Defines the member, depending on auto_accept_member property of the community
        member = Member(user=user, community=community, role="2", status="0")
        if community.auto_accept_member:
            member.status = "1"
        # Register user as new member
        member.save(force_insert=True)
        self.log(member, ADDITION, None, "User '" + str(user) + "' joined community '" + community.name
                                         + "' (" + str(community.id) + ")")
        Notifier.notify_new_member(member)
        return Response(MemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @link(permission_classes=[IsJWTAuthenticated()])
    def list_my_memberships(self, request, pk=None):
        """
        List the communities the authenticated user is member of.

                | **permission**: JWTAuthenticated
                | **endpoint**: /communities/0/list_my_memberships/
                | **method**: GET
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - count (integer)
                |       - results (members)
                |           - community
                |               - url (string)
                |               - name (string)
                |               - description (text)
                |               - creation date (datetime)
                |           - status ('0', '1', '2')
                |           - role ('0', '1', '2')
                |           - registration_date (datetime)
                |           - last_modification_date (datetime)
                |       - previous (string)
                |       - next (string))
                | **other actions**:
                |       None

        """
        my_members = Member.objects.filter(user=self.request.user)
        page = self.paginate_queryset(my_members)
        if page is not None:
            serializer = self.get_custom_pagination_serializer(page, MyMembersSerializer)
        else:
            serializer = MyMembersSerializer(self.object_list, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], permission_classes=[IsJWTAuthenticated()])
    def leave_community(self, request, pk=None):
        """
        Leave a community.

                | **permission**: JWTAuthenticated
                | **endpoint**: /communities/{id}/leave_community/
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                | **data return**:
                |       None
                | **other actions**:
                |       None

        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        user = self.request.user
        if not Member.objects.filter(user=user, community=community).exists():
            return Response({'detail': 'You are not a member of this community'},
                            status=status.HTTP_400_BAD_REQUEST)
        member = Member.objects.get(user=user, community=community)
        if member.status == '2':
            return Response({'detail': 'You have been banned from this community. You cannot leave it.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        self.log(member, DELETION, None, "User '" + str(user) + "' left community '" + community.name
                                         + "' (" + str(community.id) + ")")
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=['POST'], permission_classes=[IsJWTAuthenticated()])
    def am_i_member(self, request, pk=None):
        """
        Checks if an authenticated user is a member of the community

                | **permission**: JWTAuthenticated
                | **endpoint**: /communities/{id}/am_i_member/
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                |       - 401 Unauthorized
                | **data return**:
                |       - is_member (boolean)
                | **other actions**:
                |       None

        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        is_member = Member.objects.filter(user=self.request.user, community=community).exists()
        return Response({'is_member': is_member}, status=status.HTTP_200_OK)

    @link()
    def get_my_membership(self, request, pk=None):
        """ """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        user = self.request.user
        if not Member.objects.filter(user=user, community=community).exists():
            return Response({}, status=status.HTTP_200_OK)
        member = Member.objects.get(user=user, community=community)
        serializer = MemberSerializer(member, many=False)
        return Response(serializer.data, status=status.HTTP_200_OK)

    ## Moderator actions

    @link(permission_classes=[IsCommunityModerator])
    def retrieve_members(self, request, pk=None):
        """
        List all members belonging to a community.

                | **permission**: Community moderator
                | **endpoint**: /communities/{id}/retrieve_members/
                | **method**: GET
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - count (integer)
                |       - results (members)
                |           - id (integer)
                |           - user
                |               - url (string)
                |               - username (string)
                |               - id (integer)
                |           - status ('0', '1', '2')
                |           - role ('0', '1', '2')
                |           - registration_date (datetime)
                |           - last_modification_date (datetime)
                |       - previous (string)
                |       - next (string)
                | **other actions**:
                |       None

        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        # Check if user is a community moderator
        if not self.check_moderator_permission(self.request.user, community):
            return Response({'detail': 'Community moderator\' rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        qs = Member.objects.filter(community=community)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_custom_pagination_serializer(page, ListCommunityMembersSerializer)
        else:
            serializer = ListCommunityMembersSerializer(self.object_list, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], permission_classes=[IsCommunityModerator])
    def accept_member(self, request, pk=None):
        """
        Accept a membership request (can also be used to change member status from 'banned' back to 'accepted').

                | **permission**: Community moderator
                | **endpoint**: /communities/{id}/accept_member/
                | **method**: POST
                | **attr**:
                |       - Member object information
                |           - id (integer)
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - Modified member object
                |           - id (integer)
                |           - user
                |               - url (string)
                |               - username (string)
                |               - id (integer)
                |           - status ('0', '1', '2')
                |           - role ('0', '1', '2')
                |           - registration_date (datetime)
                |           - last_modification_date (datetime)
                | **other actions**:
                |       None

        """
        member, response = self.validate_external_object(Member, 'id', request)
        if not member:
            return response
        if not self.check_moderator_permission(self.request.user, member.community):
            return Response({'detail': 'Community moderator\' rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        member.status = '1'
        member.save()
        send_mail('[Smartribe] Membership accepted',
                  'Congratulations!\n\n' +
                  'You have been accepted as a new member of the community '+member.community.__str__(),
                  'noreply@smartribe.fr',
                  [member.user.email])
        serializer = ListCommunityMembersSerializer(member, many=False)
        self.log(member, CHANGE, None, "User '" + str(member.user) + "' accepted as member of community '"
                                       + member.community.name + "' (" + str(member.community.id) + ")")
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], permission_classes=[IsCommunityModerator])
    def ban_member(self, request, pk=None):
        """
        Ban a member from community.

                | **permission**: Community moderator
                | **endpoint**: /communities/{id}/ban_member/
                | **method**: POST
                | **attr**:
                |       - Member object information
                |           - id (integer)
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - Modified member object
                |           - id (integer)
                |           - user
                |               - url (string)
                |               - username (string)
                |               - id (integer)
                |           - status ('0', '1', '2')
                |           - role ('0', '1', '2')
                |           - registration_date (datetime)
                |           - last_modification_date (datetime)
                | **other actions**:
                |       None

        """
        member, response = self.validate_external_object(Member, 'id', request)
        if not member:
            return response
        if not self.check_upper_permission(self.request.user, member):
            return Response({'detail': 'Action not allowed.'}, status=status.HTTP_401_UNAUTHORIZED)
        member.status = '2'
        member.save()
        send_mail('[Smartribe] Membership cancelled',
                  'Sorry!\n\n' +
                  'You have been banned from the community ' + member.community.__str__(),
                  'noreply@smartribe.fr',
                  [member.user.email])
        serializer = ListCommunityMembersSerializer(member, many=False)
        self.log(member, CHANGE, None, "User '" + str(member.user) + "' banned from community '"
                                       + member.community.name + "' (" + str(member.community.id) + ")")
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], permission_classes=[IsCommunityModerator])
    def unban_member(self, request, pk=None):
        """ """
        member, response = self.validate_external_object(Member, 'id', request)
        if not member:
            return response
        if not self.check_upper_permission(self.request.user, member):
            return Response({'detail': 'Action not allowed.'}, status=status.HTTP_401_UNAUTHORIZED)
        member.status = '1'
        member.save()
        send_mail('[Smartribe] Membership reactivated',
                  'Congratulations!\n\n' +
                  'You have been accepted as a member of the community ' + member.community.__str__(),
                  'noreply@smartribe.fr',
                  [member.user.email])
        serializer = ListCommunityMembersSerializer(member, many=False)
        self.log(member, CHANGE, None, "User '" + str(member.user) + "' unbanned from community '"
                                       + member.community.name + "' (" + str(member.community.id) + ")")
        return Response(serializer.data, status=status.HTTP_200_OK)

    ## Owner actions

    @action(methods=['POST', ], permission_classes=[IsCommunityOwner])
    def promote_moderator(self, request, pk=None):
        """
        Grant community moderator rights to a member.

                | **permission**: Community owner
                | **endpoint**: /communities/{id}/promote_moderator/
                | **method**: POST
                | **attr**:
                |       - Member object information
                |           - id (integer)
                | **http return**:
                |       - 200 OK
                |       - 401 Unauthorized
                |       - 403 Forbidden
                | **data return**:
                |       - Modified member object
                |           - id (integer)
                |           - user
                |               - url (string)
                |               - username (string)
                |               - id (integer)
                |           - status ('0', '1', '2')
                |           - role ('0', '1', '2')
                |           - registration_date (datetime)
                |           - last_modification_date (datetime)
                | **other actions**:
                |       None

        """
        member, response = self.validate_external_object(Member, 'id', request)
        if not member:
            return response
        if not self.check_owner_permission(self.request.user, member.community):
            return Response({'detail': 'Community owner\' rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        member.role = '1'
        member.save()
        serializer = ListCommunityMembersSerializer(member, many=False)
        self.log(member, CHANGE, None, "User '" + str(member.user) + "' granted as moderator of community '"
                                       + member.community.name + "' (" + str(member.community.id) + ")")
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(methods=['POST', ], permission_classes=[IsCommunityOwner])
    def cancel_moderator(self, request, pk=None):
        """ """
        member, response = self.validate_external_object(Member, 'id', request)
        if not member:
            return response
        if not self.check_owner_permission(self.request.user, member.community):
            return Response({'detail': 'Community owner\' rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        member.role = '2'
        member.save()
        serializer = ListCommunityMembersSerializer(member, many=False)
        self.log(member, CHANGE, None, "User '" + str(member.user) + "' cancelled as moderator of community '"
                                       + member.community.name + "' (" + str(member.community.id) + ")")
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Location management

    ## Member actions

    @action(methods=['POST'])
    def add_location(self, request, pk=None):
        """
        Add a location to local community.

                | **permission**: Community member
                | **endpoint**: /local_communities/{id}/add_location/
                | **method**: POST
                | **attr**:
                |       - name (char 50)
                |       - description (text)
                |       - gps_x (float)
                |       - gps_y (float)
                |       - index (integer) optional
                |       - community added automatically by server
                | **http return**:
                |       - 201 Created
                |       - 400 Bad request
                |       - 401 Unauthorized
                |       - 403 Forbidden
                |       - 404 Not found
                | **data return**:
                |       Location data
                | **other actions**:
                |       None

        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        if not self.check_member_permission(self.request.user, community):
            return Response({'detail': 'Community member rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        data = request.DATA
        data['community'] = pk
        location = LocationCreateSerializer(data=data)
        if not location.is_valid():
            return Response(location.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            self.pre_add_location(data, community)
        except Exception:
            return Response({'detail': 'Bad or missing index.'}, status=status.HTTP_400_BAD_REQUEST)
        loc = location.save(force_insert=True)
        self.log(loc, ADDITION, None, "Location '" + str(loc) + "' added for community '"
                                      + community.name + "' (" + str(community.id) + ")")
        return Response(location.data, status=status.HTTP_201_CREATED)

    def pre_add_location(self, data, community):
        """
        For indexes management.
        Might be overridden by child classes.
        """
        pass

    @link()
    def list_locations(self, request, pk=None):
        """
        List all locations associated with a local community.

                | **permission**: Community member
                | **endpoint**: /communities/{id}/list_locations/
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                |       - 401 Unauthorized
                |       - 403 Forbidden
                |       - 404 Not found
                | **data return**:
                |       - count (integer)
                |       - results (locations)
                |           - community (integer)
                |           - name (char 50)
                |           - description (text)
                |           - gps_x (float)
                |           - gps_y (float)
                |       - previous (string)
                |       - next (string)
                | **other actions**:
                |       None

        """
        loc_community, response = self.validate_object(request, pk)
        if not loc_community:
            return response
        if not self.check_member_permission(self.request.user, loc_community):
            return Response({'detail': 'Community member rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        locations = Location.objects.filter(community=pk)

        page = self.paginate_queryset(locations)
        if page is not None:
            serializer = self.get_custom_pagination_serializer(page, LocationSerializer)
        else:
            serializer = LocationSerializer(self.object_list, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @link()
    def search_locations(self, request, pk=None):
        """
        Search for locations associated with a local community.

                | **permission**: Community member
                | **endpoint**: /communities/{id}/search_locations/
                | **method**: POST
                | **attr**:
                |       - search (char 255)
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                |       - 401 Unauthorized
                |       - 403 Forbidden
                |       - 404 Not found
                | **data return**:
                |       - Location list :
                |           - community (integer)
                |           - name (char 50)
                |           - description (text)
                |           - gps_x (float)
                |           - gps_y (float)
                | **other actions**:
                |       None

        """
        loc_community, response = self.validate_object(request, pk)
        if not loc_community:
            return response
        if not self.check_member_permission(self.request.user, loc_community):
            return Response({'detail': 'Community member rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        data = request.QUERY_PARAMS
        if 'search' not in data:
            return Response({'detail': 'search parameter missing.'}, status=status.HTTP_400_BAD_REQUEST)
        locations = Location.objects.filter(Q(community=pk),
                                            Q(name__icontains=data['search']) |
                                            Q(description__icontains=data['search']))

        page = self.paginate_queryset(locations)
        if page is not None:
            serializer = self.get_custom_pagination_serializer(page, LocationSerializer)
        else:
            serializer = LocationSerializer(self.object_list, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

    ## Moderator actions

    @action(methods=['POST'])
    def delete_location(self, request, pk=None):
        """
        Delete a location.

                | **permission**: Community moderator
                | **endpoint**: /local_communities/{id}/delete_location/
                | **method**: POST
                | **attr**:
                |       - id (integer)
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                |       - 401 Unauthorized
                |       - 403 Forbidden
                |       - 404 Not found
                | **data return**:
                |       None
                | **other actions**:
                |       None
        """
        community, response = self.validate_object(request, pk)
        if not community:
            return response
        if not self.check_moderator_permission(self.request.user, community):
            return Response({'detail': 'Community member rights required.'}, status=status.HTTP_401_UNAUTHORIZED)
        location, response = self.validate_external_object(Location, 'id', request)
        if not location:
            return response

        """data = request.DATA
        if 'id' not in data:
            return Response({'detail': 'No location id provided.'}, status=status.HTTP_400_BAD_REQUEST)
        if not Location.objects.filter(community=pk, id=data['id']).exists():
            return Response({'detail': 'No such location.'}, status=status.HTTP_404_NOT_FOUND)
        location = Location.objects.get(id=data['id'])"""
        try:
            self.pre_delete_location(location, community)
        except Exception:
            return Response({'detail': 'Bad operation.'}, status=status.HTTP_400_BAD_REQUEST)
        self.log(location, DELETION, None, "Location '" + str(location) + "' deleted for community '"
                                           + community.name + "' (" + str(community.id) + ")")
        location.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def pre_delete_location(self, location, community):
        """
        For indexes management.
        Might be overridden by child classes.
        """
        pass

    # Get communities lists

    @link(permission_classes=[IsJWTAuthenticated()])
    def get_shared_communities(self, request, pk=None):
        """
         Get communities shared by two users
        """
        """data = request.QUERY_PARAMS
        if 'other_user' not in data:
            return Response({'detail': 'Missing other_user id'}, status=status.HTTP_400_BAD_REQUEST)
        if not get_user_model().objects.filter(pk=data['other_user']).exists():
            return Response({'detail': 'No other_user with this id'}, status=status.HTTP_400_BAD_REQUEST)
        other_user = get_user_model().objects.get(pk=data['other_user'])"""

        other_user, response = self.validate_external_object(get_user_model(), 'other_user', request)
        if not other_user:
            return response


        user_communities = Member.objects.filter(user=self.request.user, status='1').values('community')
        other_user_communities = Member.objects.filter(user=other_user, status='1').values('community')
        shared_communities = Community.objects.filter(Q(id__in=user_communities) & Q(id__in=other_user_communities))
        page = self.paginate_queryset(shared_communities)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(shared_communities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @link(permission_classes=[IsJWTAuthenticated()])
    def get_offer_communities(self, request, pk=None):
        """
         Get relevant meeting points for an offer
        """
        user = self.request.user
        """data = request.QUERY_PARAMS
        if 'offer' not in data:
            return Response({'detail': 'Missing offer id'}, status=status.HTTP_400_BAD_REQUEST)
        if not Offer.objects.filter(pk=data['offer']).exists():
            return Response({'detail': 'No offer with this id'}, status=status.HTTP_400_BAD_REQUEST)
        offer = Offer.objects.get(pk=data['offer'])"""

        offer, response = self.validate_external_object(Offer, 'offer', request)
        if not offer:
            return response


        req = offer.request
        if user != offer.user and user != req.user:
            return Response({'detail': 'Operation not allowed'}, status=status.HTTP_403_FORBIDDEN)
        if user == offer.user:
            other_user = req.user
        else:
            other_user = offer.user
        if req.community:
            shared_communities = Community.objects.filter(id=req.community.id)
        else:
            user_communities = Member.objects.filter(user=user, status='1').values('community')
            other_user_communities = Member.objects.filter(user=other_user, status='1').values('community')
            shared_communities = Community.objects.filter(Q(id__in=user_communities) & Q(id__in=other_user_communities))
        page = self.paginate_queryset(shared_communities)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(shared_communities, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    ## Community permissions

    def check_member_permission(self, user, community):
        """
        Verifies that user has member's rights on the community
        """
        if not user:
            return False
        elif Member.objects.filter(
                user=user,
                community=community,
                status="1"
        ).exists():
            return True
        else:
            return False

    def check_moderator_permission(self, user, community):
        """
        Verifies that user has moderator's rights on the community
        """
        # user, response = AuthUser().authenticate(self.request)
        if not user:
            return False
        elif Member.objects.filter(
                Q(user=user),
                Q(community=community),
                Q(status="1"),
                Q(role="1") | Q(role="0")
        ).exists():
            return True
        else:
            return False

    def check_owner_permission(self, user, community):
        """
        Verifies that user has owner's rights on the community
        """
        if not user:
            return False
        elif Member.objects.filter(
                user=user,
                community=community,
                status="1",
                role="0"
        ).exists():
            return True
        else:
            return False

    def check_upper_permission(self, user, member):
        """
        Verifies that user has upper rights on community than the member he wants to manage
        """
        if not user:
            return False
        if not Member.objects.filter(user=user, community=member.community).exists():
            return False
        m_user = Member.objects.get(user=user, community=member.community)
        if int(m_user.role) < int(member.role):
            return True
        return False

    # TOOLS

    def get_custom_pagination_serializer(self, page, serializer_class):
        """
        Return a serializer instance to use with paginated data.
        """
        class SerializerClass(self.pagination_serializer_class):
            class Meta:
                object_serializer_class = serializer_class

        pagination_serializer_class = SerializerClass
        context = self.get_serializer_context()
        return pagination_serializer_class(instance=page, context=context)