

class BaseModelMixin(object):

    @classmethod
    def get_app_label(cls):
        return cls._meta.app_label

    @classmethod
    def get_model_name(cls):
        return cls._meta.object_name.lower()

    @classmethod
    def get_verbose_name(cls):
        return cls._meta.verbose_name

