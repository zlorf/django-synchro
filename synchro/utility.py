from datetime import datetime

from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db.models import Manager, Model
from django.db.models.base import ModelBase


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


class _NaturalKeyModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        parents = [b for b in bases if isinstance(b, _NaturalKeyModelBase)]
        if not parents:
            return super(_NaturalKeyModelBase, cls).__new__(cls, name, bases, attrs)
        kwargs = {}
        if 'objects' in attrs:
            kwargs['manager'] = attrs['objects'].__class__
        kwargs.update(attrs.pop('_natural_manager_kwargs', {}))
        attrs['objects'] = NaturalManager(*attrs['_natural_key'], **kwargs)
        return super(_NaturalKeyModelBase, cls).__new__(cls, name, bases, attrs)


class NaturalKeyModel(Model):
    __metaclass__ = _NaturalKeyModelBase
    _natural_key = ()

    def natural_key(self):
        return tuple(getattr(self, field) for field in self._natural_key)

    class Meta:
        abstract = True


def reset_synchro():
    from models import ChangeLog, Reference, options
    options.last_check = datetime.now()
    ChangeLog.objects.all().delete()
    Reference.objects.all().delete()
