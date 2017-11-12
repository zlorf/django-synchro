from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def get_all_models(app):
    try:
        app_conf = apps.get_app_config(app)
    except LookupError:
        for config in apps.get_app_configs():
            if config.name == app:
                app_conf = config
                break
    return app_conf.get_models()


def gel_listed_models(app, l):
    def parse(model):
        m = apps.get_model(app, model)
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


def _get_remote_field(m2m):
    return m2m.remote_field if hasattr(m2m, 'remote_field') else m2m.related

def get_intermediary(models):
    res = {}
    for model in models:
        res.update((m2m.rel.through, _get_remote_field(m2m)) for m2m in model._meta.many_to_many
                   if not m2m.rel.through._meta.auto_created)
    return res

MODELS = INTER_MODELS = []


def prepare():
    global MODELS, INTER_MODELS
    MODELS = parse_models(getattr(settings, 'SYNCHRO_MODELS', ()))
    # Since user-defined m2m intermediary objects don't send m2m_changed signal,
    #  we need to listen to those models.
    INTER_MODELS = get_intermediary(MODELS)

if apps.ready:
    # In order to prevent exception in Django 1.7
    prepare()

REMOTE = getattr(settings, 'SYNCHRO_REMOTE', None)
LOCAL = 'default'
ALLOW_RESET = getattr(settings, 'SYNCHRO_ALLOW_RESET', True)
DEBUG = getattr(settings, 'SYNCHRO_DEBUG', False)

if REMOTE is None:
    if not hasattr(settings, 'SYNCHRO_REMOTE'):
        import warnings
        warnings.warn('SYNCHRO_REMOTE not specified. Synchronization is disabled.', RuntimeWarning)
elif REMOTE not in settings.DATABASES:
    raise ImproperlyConfigured('SYNCHRO_REMOTE invalid - no such database: %s.' % REMOTE)
