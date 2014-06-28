from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
import core.utils


class CommunityTests(APITestCase):
    def setUp(self):
        """
        Make a user for authenticating and
        testing community actions
        """
        user = User(username="testcommunity", password="test")
        user.save()

    def test_create_community_without_auth(self):
        """
        Ensure we cannot create community
        """
        url = '/api/v1/communities/'
        data = {
            'name': 'com1',
            'description': 'com1desc',
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_community_with_auth(self):
        """
        Ensure we can create community when we are authenticated
        """
        # Generate token for testcommunity user
        user = User.objects.get(username="testcommunity")
        token = core.utils.gen_auth_token(user)
        auth = 'JWT {0}'.format(token)

        url = '/api/v1/communities/'
        data = {
            'name': 'com1',
            'description': 'com1desc',
        }

        response = self.client.post(url, data, HTTP_AUTHORIZATION=auth,
                                    format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_modify_community_with_auth(self):
        # Generate token for testcommunity user
        user = User.objects.get(username="testcommunity")
        token = core.utils.gen_auth_token(user)
        auth = 'JWT {0}'.format(token)

        url = '/api/v1/communities/1/'
        data = {
            'name': 'com1',
            'description': 'com1descmodify',
        }

        response = self.client.put(url, data, HTTP_AUTHORIZATION=auth,
                                   format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['description'], 'com1descmodify')

    def test_delete_community_with_auth(self):
        """
        Ensure we can delete community when we are authenticated
        """
        # Generate token for testcommunity user
        user = User.objects.get(username="testcommunity")
        token = core.utils.gen_auth_token(user)
        auth = 'JWT {0}'.format(token)

        url = '/api/v1/communities/1/'

        response = self.client.delete(url, HTTP_AUTHORIZATION=auth)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
