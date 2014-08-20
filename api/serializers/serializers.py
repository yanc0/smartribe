from django.contrib.auth.models import User, Group, Permission
from rest_framework.authtoken.models import Token
from core.models import Profile, Skill, Community, Request, Offer, Member
from rest_framework import serializers


# USER
from core.models.address import Address
from core.models.skill import SkillCategory


class UserCreateSerializer(serializers.HyperlinkedModelSerializer):
   
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'password', 'groups', 'is_active')
        write_only_fields = ('password',)


class UserPublicSerializer(serializers.HyperlinkedModelSerializer):
   
    class Meta:
        model = User
        fields = ('url', 'username', 'id')
        read_only_fields = ('username',)


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'password', 'groups')
        read_only_fields = ('username',)
        write_only_fields = ('password',)


# GROUP

class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ('url', 'name', 'permissions')


# TOKEN

class TokenSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Token
        fields = ('user', 'key')


class PermissionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Permission
        fields = ('url', 'name', 'codename')


#   ADDRESS

class AddressSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Address
        fields = ('num', 'street', 'city', 'zip_code', 'country')


# PROFILE

class ProfileCreateSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.PrimaryKeyRelatedField()
    address = AddressSerializer(many=False, blank=True)

    class Meta:
        model = Profile
        fields = ('url', 'user', 'gender', 'address', 'phone', 'birthdate', 'bio', 'photo', 'favorite_contact')


class ProfileSerializer(serializers.HyperlinkedModelSerializer):
    address = AddressSerializer(many=False, blank=True)

    class Meta:
        model = Profile
        fields = ('url', 'user', 'gender', 'address', 'phone', 'birthdate', 'bio', 'photo', 'favorite_contact')
        read_only_fields = ('user',)


# SKILL

class SkillCategorySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = SkillCategory
        fields = ('url', 'name', 'detail')


class SkillCreateSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.PrimaryKeyRelatedField()
    category = serializers.PrimaryKeyRelatedField()

    class Meta:
        model = Skill
        fields = ('url', 'user', 'category', 'description')


class SkillSerializer(serializers.HyperlinkedModelSerializer):
    user = serializers.PrimaryKeyRelatedField()
    category = serializers.PrimaryKeyRelatedField()

    class Meta:
        model = Skill
        fields = ('url', 'user', 'category', 'description')
        read_only_fields = ('user',)



# REQUEST


class OfferSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Offer
        fields = ('request', 'description')
