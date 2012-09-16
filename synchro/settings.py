from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import get_app, get_models, get_model


def get_all_models(app):
    return get_models(get_app(app))


def gel_listed_models(app, l):
    def parse(model):
        m = get_model(app, model)
        if m is None:
            raise ImproperlyConfigured(
                'SYNCHRO_MODELS: Model %s not found in %s app.' % (model, app))
        return m
    return map(parse, l)


def parse_models(l):
    res = []
    for entry in l:
        if len(entry) == 1:
            entry = entry[0]
        if type(entry) == str:
            res.extend(get_all_models(entry))
        else:
            app = entry[0]
            res.extend(gel_listed_models(app, entry[1:]))
    return res


def get_intermediary(models):
    res = {}
    for model in models:
        res.update((m2m.rel.through, m2m.related) for m2m in model._meta.many_to_many
                   if not m2m.rel.through._meta.auto_created)
    return res


MODELS = parse_models(getattr(settings, 'SYNCHRO_MODELS', ()))
# Since user-defined m2m intermediary objects don't send m2m_changed signal, we need to listen to
# those models.
INTER_MODELS = get_intermediary(MODELS)
REMOTE = getattr(settings, 'SYNCHRO_REMOTE', None)
LOCAL = 'default'

if REMOTE is None:
    if not hasattr(settings, 'SYNCHRO_REMOTE'):
        import  warnings
        warnings.warn('SYNCHRO_REMOTE not specified. Synchronization is disabled.', RuntimeWarning)
elif REMOTE not in settings.DATABASES:
    raise ImproperlyConfigured('SYNCHRO_REMOTE invalid - no such database: %s.' % REMOTE)
