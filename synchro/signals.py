from functools import wraps

from django.db.models.signals import post_save, post_delete


def synchro_connect():
    from models import save_changelog_add_chg, save_changelog_del
    post_save.connect(save_changelog_add_chg, dispatch_uid='synchro_add_chg')
    post_delete.connect(save_changelog_del, dispatch_uid='synchro_del')


def synchro_disconnect():
    post_save.disconnect(dispatch_uid='synchro_add_chg')
    post_delete.disconnect(dispatch_uid='synchro_del')


class DisableSynchroLog(object):
    def __enter__(self):
        synchro_disconnect()

    def __exit__(self, *args, **kwargs):
        synchro_connect()
        return False


def disable_synchro_log(f):
    @wraps(f)
    def inner(*args, **kwargs):
        with DisableSynchroLog():
            return f(*args, **kwargs)
    return inner
