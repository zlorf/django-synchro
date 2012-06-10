django-synchro
==============

TODO:
write pretty usage readme;
write rich tests;


AIM:
This app is for synchronization of django objects between databases.

Consider scenario:
- there is one production projects deployed on the web
- and the same project is deployed on some office computer in case of main server failure

Assuming that local database is regularly synced (eg. once a day main database is exported and imported into local system),
in case of long main server failure staff may use local project (inserting objects etc.).
After server is up again, local changes (from the point of last checkpoint) can be synchronized to remote server.


USAGE:

Install app (please note django-dbsettings requirement and its install notes, such as cache backend important remarks)

Configure DATABASES

Add synchro to INSTALLED_APPS

Specify in your settings which models should be watched and synchronized:

SYNCHRO_REMOTE = 'remote'
SYNCHRO_MODELS = (
    'my_first_app', # all models
    ('my_second_app', 'model1', 'model2'), # listed models
    'my_third_app', # all models again
)


TO SYNCHRONIZE:
$ ./manage.py synchronize

SYNCHRO ADMIN VIEW:

Include in your urls:

url(r'^synchro/', include('synchro.urls', 'synchro', 'synchro')),

Then the view will be available at reversed url: synchro:synchro


REMARKS:

For efficient objects finding, provide natural_key and get_by_natural_key.
Short way of writing manager is provided.

from synchro import natural_manager

class MyModel(models.Model):
    ...
    objects = natural_manager('code', 'day')
    def natural_key(self):
        return self.code, self.day


If your model has some fields that should not be synchronized (eg. field with payment balances, which is computed based on orders - in order.post_save signal):

SYNCHRO_SKIP = ('balance',)


If you want to not log some actions:

from synchro import DisableSynchroLog

with DisableSynchroLog():
    mymodel.name = foo
    mymodel.save()


If your signal handlers modify other objects, such action will be probably reproduced twice:
- once when model will be updated on REMOTE, then REMOTE signal handler will fire
- second time, because original signal handler's action was logged, the modified object will be synchronized
To prevent this, wrap handler with DisableSynchroLog:

@receiver(models.signals.post_delete, sender=Parcel)
def update_agent_balance_delete(sender, instance, *args, **kwargs):
    with DisableSynchroLog():
        instance.agent.balance -= float(instance.payment_left))
        instance.agent.save()

Or with decorator:

@receiver(models.signals.post_delete, sender=Parcel)
@disable_synchro_log
def update_agent_balance_delete(sender, instance, *args, **kwargs):
    instance.agent.balance -= float(instance.payment_left))
    instance.agent.save()

Using decorator, be sure to place it after connecting to signal, not before - otherwise it won't work.


If you wish to reset sychronization status:

from synchro import reset_synchro
reset_synchro()

Or ugly way of changing synchro checkpoint:

from synchro.models import options
options.last_check = datetime.datetime.now()
