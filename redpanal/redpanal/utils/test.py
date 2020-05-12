import abc
from django.urls import reverse

class InstanceTestMixin(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def create_instance(self):
        pass

    @abc.abstractmethod
    def get_model_name(self):
        pass

    def test_view_detail(self):
        instance = self.create_instance()

        response = self.client.get(instance.get_absolute_url())
        self.assertEqual(200, response.status_code)

    def test_get_create_view_redirect_unauthenticated(self):
        response = self.client.get(reverse('%s-create' % self.get_model_name()))
        self.assertEqual(302, response.status_code)

    def test_get_create_view(self):
        self.login()
        response = self.client.get(reverse('%s-create' % self.get_model_name()))
        self.assertEqual(200, response.status_code)

    def test_get_edit_view(self):
        instance = self.create_instance()
        self.login()
        response = self.client.get(reverse('%s-edit' % self.get_model_name(),
                                           args=[instance.slug]))
        self.assertEqual(200, response.status_code)

    def test_get_delete_view(self):
        instance = self.create_instance()
        self.login()
        response = self.client.get(reverse('%s-delete' % self.get_model_name(),
                                           args=[instance.slug]))
        self.assertEqual(200, response.status_code)
