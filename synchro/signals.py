from functools import wraps

from django.db.models.signals import post_save, post_delete, m2m_changed


def synchro_connect():
    from handlers import save_changelog_add_chg, save_changelog_del, save_changelog_m2m
    post_save.connect(save_changelog_add_chg, dispatch_uid='synchro_add_chg')
    post_delete.connect(save_changelog_del, dispatch_uid='synchro_del')
    m2m_changed.connect(save_changelog_m2m, dispatch_uid='synchro_m2m')


def synchro_disconnect():
    post_save.disconnect(dispatch_uid='synchro_add_chg')
    post_delete.disconnect(dispatch_uid='synchro_del')
    m2m_changed.disconnect(dispatch_uid='synchro_m2m')


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
