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


MODELS = parse_models(getattr(settings, 'SYNCHRO_MODELS', ()))
REMOTE = getattr(settings, 'SYNCHRO_REMOTE', None)
LOCAL = 'default'

if REMOTE not in settings.DATABASES:
    raise ImproperlyConfigured('SYNCHRO_REMOTE not specified or invalid.')
