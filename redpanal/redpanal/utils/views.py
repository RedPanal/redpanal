from django.core.exceptions import PermissionDenied
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required

class LoginRequiredMixin(object):

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(LoginRequiredMixin, self).dispatch(*args, **kwargs)


class UserRequiredMixin(object):

    def get_object(self, queryset=None):
        object = super(UserRequiredMixin, self).get_object(queryset)
        if object.user == self.request.user:
            return object
        else:
            raise PermissionDenied

