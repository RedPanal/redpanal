from django.test import TestCase
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

class UsersTest(TestCase):
    def test_user_list_view(self):
        user = User.objects.create_user('john', 'bonham@zeppelin.rock', 'johnpass')
        response = self.client.get(reverse('user-list'))
        self.assertContains(response, 'john')

