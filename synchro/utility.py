from datetime import datetime

from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db.models import Manager


class NaturalManager(Manager):
    def __init__(self, fields, allow_many=False):
        super(NaturalManager, self).__init__()
        self.fields = fields
        self.allow_many = allow_many

    def get_by_natural_key(self, *args):
        lookups = dict(zip(self.fields, args))
        try:
            return self.get(**lookups)
        except MultipleObjectsReturned:
            if self.allow_many:
                return self.filter(**lookups)[0]
            raise


def natural_manager(*fields, **kwargs):
    manager = kwargs.get('manager', Manager)
    allow_many = kwargs.get('allow_many', False)
    if manager == Manager:
        return NaturalManager(fields, allow_many)
    else:
        if not issubclass(manager, Manager):
            raise ValidationError(
                '%s manager class must be a subclass of django.db.models.Manager'
                % manager.__name__)
        class NewNaturalManager(NaturalManager, manager):
            pass
        return NewNaturalManager(fields, allow_many)


def reset_synchro():
    from models import ChangeLog, Reference, options
    options.last_check = datetime.now()
    ChangeLog.objects.all().delete()
    Reference.objects.all().delete()
