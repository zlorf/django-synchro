from django.apps import AppConfig


class SynchroConfig(AppConfig):
    name = 'synchro'
    verbose_name = 'Synchro'

    def ready(self):
        from signals import synchro_connect
        synchro_connect()
