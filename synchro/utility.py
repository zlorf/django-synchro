from datetime import datetime

from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db.models import Manager


class NaturalManager(Manager):
    """
    Manager must be able to instantiate without arguments in order to work with M2M.
    Hence this machinery to store arguments in class.
    Somehow related to Django bug #13313.
    """

    def __new__(cls, *fields, **options):
        """
        Creates actual manager, which can be further subclassed and instantiated without arguments.
        """
        assert fields, 'No fields specified in %s constructor' % cls
        _fields = fields
        _allow_many = options.get('allow_many', False)
        manager = options.get('manager', Manager)
        if not issubclass(manager, Manager):
            raise ValidationError(
                '%s manager class must be a subclass of django.db.models.Manager.'
                % manager.__name__)

        class NewNaturalManager(cls, manager):
            fields = _fields
            allow_many = _allow_many

            def __init__(self, *args, **kwargs):
                # Intentionally ignore arguments
                super(NewNaturalManager, self).__init__()

            def __new__(cls, *args, **kwargs):
                # Skip NaturalManager.__new__ because `fields` are already defined
                return super(NaturalManager, cls).__new__(cls, *args, **kwargs)

            def get_by_natural_key(self, *args):
                lookups = dict(zip(self.fields, args))
                try:
                    return self.get(**lookups)
                except MultipleObjectsReturned:
                    if self.allow_many:
                        return self.filter(**lookups)[0]
                    raise
        return super(NaturalManager, cls).__new__(NewNaturalManager)


def natural_manager(*args, **kwargs):
    """Function left for backward-compatibility"""
    import warnings
    warnings.warn('natural_manager function is deprecated - use NaturalManager instead.', DeprecationWarning)
    return NaturalManager(*args, **kwargs)


def reset_synchro():
    from models import ChangeLog, Reference, options
    options.last_check = datetime.now()
    ChangeLog.objects.all().delete()
    Reference.objects.all().delete()
