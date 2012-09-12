from datetime import datetime

from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db.models import Manager


class NaturalManager(Manager):
    def __init__(self, **kwargs):
        """
        Manager must be able to instantiate without parameters in order to work with M2M.
        Somehow related to Django bug #13313.
        """
        for arg in ('fields', 'allow_many'):
            if arg in kwargs:
                setattr(self, arg, kwargs.pop(arg))
            assert hasattr(self, arg),\
                'No %s property found in object. Pass keyword to __init__' % arg
        super(NaturalManager, self).__init__(**kwargs)

    def get_by_natural_key(self, *args):
        lookups = dict(zip(self.fields, args))
        try:
            return self.get(**lookups)
        except MultipleObjectsReturned:
            if self.allow_many:
                return self.filter(**lookups)[0]
            raise


def natural_manager(*_fields, **kwargs):
    manager = kwargs.get('manager', Manager)
    _allow_many = kwargs.get('allow_many', False)
    if not issubclass(manager, Manager):
        raise ValidationError(
            '%s manager class must be a subclass of django.db.models.Manager'
            % manager.__name__)

    class NewNaturalManager(NaturalManager, manager):
        fields = _fields
        allow_many = _allow_many
    return NewNaturalManager()


def reset_synchro():
    from models import ChangeLog, Reference, options
    options.last_check = datetime.now()
    ChangeLog.objects.all().delete()
    Reference.objects.all().delete()
