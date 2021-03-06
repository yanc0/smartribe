from datetime import timedelta, timezone, datetime
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Min, Max
from rest_framework import viewsets
from rest_framework.decorators import action, link
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
import django_filters

from api.mail_templates.user import registration_message, recovery_password_message
from api.permissions.common import IsJWTAuthenticated, IsJWTMe
from api.serializers import UserCreateSerializer, UserPublicSerializer, UserSerializer
from api.utils.asyncronous_mail import send_mail
from core.models import ActivationToken, PasswordRecovery, Evaluation, Profile, Member, LocalCommunity
import core.utils


class UserFilter(django_filters.FilterSet):
    """
    Specific search filter for users
    """
    email = django_filters.CharFilter(name='email', lookup_type='contains')

    class Meta:
        model = get_user_model()
        fields = ['email', ]


class UserViewSet(viewsets.ModelViewSet):
    """
    Inherits standard characteristics from ModelViewSet:

            | **Endpoint**: /users/
            | **Methods**: GET / POST / PUT / PATCH / DELETE / OPTIONS
            | **Permissions**:
            |       - Default : IsJWTMe
            |       - GET : IsJWTAuthenticated
            |       - POST : AllowAny

    """
    model = get_user_model()
    serializer_class = UserSerializer
    filter_class = UserFilter

    def get_serializer_class(self):
        serializer_class = self.serializer_class
        if self.request.method == 'GET' and 'pk' not in self.kwargs:
            serializer_class = UserPublicSerializer
        elif self.request.method == 'GET' and not self.object == self.request.user:
            serializer_class = UserPublicSerializer
        elif self.request.method == 'POST':
            serializer_class = UserCreateSerializer
        return serializer_class

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsJWTAuthenticated()]
        elif self.request.method == 'POST' and 'update_my_password' in self.request.get_full_path():
            return [IsJWTAuthenticated()]
        elif self.request.method == 'POST':
            return [AllowAny()]
        else:
            return [IsJWTMe()]

    def pre_save(self, obj):
        super().pre_save(obj)
        if 'password' in self.request.DATA and self.request.DATA['password']:
            obj.password = make_password(obj.password)
        if self.request.method == 'POST':
            obj.is_active = False

    def post_save(self, obj, created=False):
        create = False
        if self.request.method == 'POST':
            create = True
            profile = Profile(user=obj)
            profile.save()
            token = ActivationToken(user=obj,
                                    token=core.utils.gen_temporary_token())
            token.save()
            subject, message = registration_message(token)
            send_mail(subject,
                      message,
                      'noreply@smartribe.fr',
                      [obj.email],
                      fail_silently=False)
            # First community registration
            if LocalCommunity.objects.filter(name=settings.INITIAL_COMMUNITY).exists():
                community = LocalCommunity.objects.get(name=settings.INITIAL_COMMUNITY)
                Member.objects.create(user=obj, community=community, role="2", status="1")

        LogEntry.objects.log_action(user_id=obj.id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=obj.id,
                                    object_repr=obj.email,
                                    action_flag=ADDITION if create else CHANGE)

    former_id = None

    def pre_delete(self, obj):
        super().pre_delete(obj)
        self.former_id = obj.id

    def post_delete(self, obj):
        super().post_delete(obj)
        LogEntry.objects.log_action(user_id=self.former_id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=self.former_id,
                                    object_repr=obj.email,
                                    action_flag=DELETION)

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)

    @action(methods=['POST', ])
    def confirm_registration(self, request, pk=None):
        """ Confirm user registration:

                | **permission**: any
                | **endpoint**: /users/{token}/confirm_registration
                | **method**: POST
                | **attr**:
                |       None
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                | **data return**:
                |       None

        """
        token = pk
        if token is None:
            return Response({"detail": "Missing token"}, status=status.HTTP_400_BAD_REQUEST)
        if not ActivationToken.objects.filter(token=token).exists():
            return Response({"detail": "Activation error"}, status=status.HTTP_400_BAD_REQUEST)
        user = ActivationToken.objects.get(token=token).user
        user.is_active = True
        user.save()
        ActivationToken.objects.get(token=token).delete()
        LogEntry.objects.log_action(user_id=user.id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=user.id,
                                    object_repr=user.email,
                                    action_flag=CHANGE,
                                    change_message="Registration confirmation")
        return Response(status=status.HTTP_200_OK)

    @action(methods=['POST', ])
    def recover_password(self, request, pk=None):
        """ Recover password

                | **permission**: any
                | **endpoint**: /users/0/recover_password/
                | **method**: POST
                | **attr**:
                |       - email: string (required)
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                |       - 401 Unauthorized
                | **data return**:
                |       None
                | **other actions**:
                |       - Sends an email with a password recovery token

        """
        data = request.DATA
        if 'email' not in data:
            return Response({"detail": "Email address required"}, status=status.HTTP_400_BAD_REQUEST)
        if not get_user_model().objects.filter(email=data['email']).exists():
            return Response({"detail": "Unknown email address"}, status=status.HTTP_400_BAD_REQUEST)
        user = get_user_model().objects.get(email=data['email'])
        ip = core.utils.get_client_ip(request)
        user_list = PasswordRecovery.objects.filter(user=user)
        if user_list.count() >= 2:
            last_pr = user_list.order_by('-pk')[1]
            fr = timezone(timedelta(hours=1), "Europe/Rome")
            delta = datetime.now(tz=fr) - last_pr.request_datetime
            if delta < timedelta(minutes=5):
                return Response({"detail": "Try again after 5 min"}, status=status.HTTP_401_UNAUTHORIZED)
        token = core.utils.gen_temporary_token()
        pr = PasswordRecovery(user=user, token=token, ip_address=ip)
        pr.save()
        subject, message = recovery_password_message(pr)
        send_mail(subject,
                  message,
                  'noreply@smartribe.fr',
                  [user.email],
                  fail_silently=False)
        LogEntry.objects.log_action(user_id=user.id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=user.id,
                                    object_repr=user.email,
                                    action_flag=CHANGE,
                                    change_message="Password recovery request")
        return Response(status=status.HTTP_200_OK)

    @action(methods=['POST', ])
    def set_new_password(self, request, pk=None):
        """ Set a new password, using password recovery token

                | **permission**: any
                | **endpoint**: /users/{token}/set_new_password/
                | **method**: POST
                | **attr**:
                |       - password: string (required)
                | **http return**:
                |       - 200 OK
                |       - 400 Bad request
                | **data return**:
                |       None
                | **other actions**:
                |       - Sends an email with a password recovery token

        """
        token = pk
        data = request.DATA
        if token is None:
            return Response({"detail": "Token required"}, status=status.HTTP_400_BAD_REQUEST)
        if not 'password' in data:
            return Response({"detail": "Password required"}, status=status.HTTP_400_BAD_REQUEST)
        if not PasswordRecovery.objects.filter(token=token).exists():
            return Response({"detail": "No password renewal request"}, status=status.HTTP_400_BAD_REQUEST)
        user = PasswordRecovery.objects.get(token=token).user
        user.password = make_password(data['password'])
        user.save()
        PasswordRecovery.objects.filter(user=user).delete()
        LogEntry.objects.log_action(user_id=user.id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=user.id,
                                    object_repr=user.email,
                                    action_flag=CHANGE,
                                    change_message="Password recovery done")
        return Response(status=status.HTTP_200_OK)

    @action(methods=['POST', ])
    def update_my_password(self, request, pk=None):
        """"""
        fields = {'password_old', 'password_new'}
        data = request.DATA
        if any(field not in data for field in fields):
            return Response({"detail": "Both old and new password are required."}, status=status.HTTP_400_BAD_REQUEST)
        if not request.user.check_password(data['password_old']):
            return Response({"detail": "Old password is not correct."}, status=status.HTTP_401_UNAUTHORIZED)
        request.user.password = make_password(data['password_new'])
        request.user.save()
        LogEntry.objects.log_action(user_id=request.user.id,
                                    content_type_id=ContentType.objects.get_for_model(self.model).pk,
                                    object_id=request.user.id,
                                    object_repr=request.user.email,
                                    action_flag=CHANGE,
                                    change_message="Password change")
        return Response(status=status.HTTP_200_OK)

    @link(permission_classes=[IsJWTAuthenticated])
    def get_my_user(self, request, pk=None):
        """
        Get current authenticated user:

                | **permission**: authenticated, get self
                | **endpoint**: /users/0/get_my_user/
                | **method**: GET
                | **http return**:
                |       - 200 OK
                |       - 403 Forbidden
                | **data return**:
                |       - url: resource
                |       - username: string
                |       - email: string
                |       - groups: array

        """
        serializer = UserSerializer(self.request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @link(permission_classes=[IsJWTAuthenticated])
    def get_user_evaluation(self, request, pk=None):
        """
        Get evaluation information for a specific user:

                | **permission**: authenticated
                | **endpoint**: /users/{id}/get_user_evaluation/
                | **method**: GET
                | **http return**:
                |       - 200 OK
                |       - 403 Forbidden
                |       - 404 Not found
                | **data return**:
                |       - average_eval (float)
                |       - min_eval(integer)
                |       - max_eval(integer)

        """
        if pk is None:
            return Response({'detail': 'Id requested in URL.'}, status.HTTP_404_NOT_FOUND)
        if not self.model.objects.filter(id=pk).exists():
            return Response({'detail': 'No such object.'}, status.HTTP_404_NOT_FOUND)
        obj = self.model.objects.get(id=pk)
        if not Evaluation.objects.filter(offer__user=obj).exists():
            eval = {}
        else:
            eval = Evaluation.objects.filter(offer__user=obj).aggregate(average_eval=Avg('mark'),
                                                                        min_eval=Min('mark'),
                                                                        max_eval=Max('mark'))
        return Response(eval, status=status.HTTP_200_OK)
