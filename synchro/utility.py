from django.core.exceptions import MultipleObjectsReturned
from django.db.models import Manager

def natural_manager(*fields, **kwargs):
    manager = kwargs.get('manager', Manager)
    allow_many = kwargs.get('allow_many', False)
    class NaturalManager(manager):
        def get_by_natural_key(self, *args):
            lookups = dict(zip(fields, args))
            try:
                return self.get(**lookups)
            except MultipleObjectsReturned:
                if allow_many:
                    return self.filter(**lookups)[0]
                raise
    return NaturalManager()
