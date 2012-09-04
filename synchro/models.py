from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
import dbsettings

#noinspection PyUnresolvedReferences
import settings  # in order to validate


ACTIONS = (
    (ADDITION, 'Add'),
    (CHANGE, 'Change'),
    (DELETION, 'Delete'),
)


class SynchroSettings(dbsettings.Group):
    last_check = dbsettings.DateTimeValue('Last synchronization')
options = SynchroSettings()


class Reference(models.Model):
    content_type = models.ForeignKey(ContentType)
    local_object_id = models.CharField(max_length=20)
    remote_object_id = models.CharField(max_length=20)

    class Meta:
        unique_together = ('content_type', 'local_object_id')


class ChangeLog(models.Model):
    content_type = models.ForeignKey(ContentType)
    object_id = models.CharField(max_length=20)
    object = generic.GenericForeignKey()
    date = models.DateTimeField(auto_now=True)
    action = models.PositiveSmallIntegerField(choices=ACTIONS)

    def __unicode__(self):
        return u'ChangeLog for %s (%s)' % (unicode(self.object), self.get_action_display())


class DeleteKey(models.Model):
    changelog = models.OneToOneField(ChangeLog)
    key = models.CharField(max_length=200)


def save_changelog_add_chg(sender, instance, created, using, **kwargs):
    if sender in settings.MODELS and using == settings.LOCAL:
        if created:
            ChangeLog.objects.create(object=instance, action=ADDITION)
        else:
            cl = ChangeLog.objects.create(object=instance, action=CHANGE)
            cls = (ChangeLog.objects.filter(content_type=cl.content_type, object_id=cl.object_id)
                   .exclude(pk=cl.pk).order_by('-date', '-pk'))
            if len(cls) > 0 and cls[0].action == CHANGE:
                cls[0].delete()


def save_changelog_del(sender, instance, using, **kwargs):
    if sender in settings.MODELS and using == settings.LOCAL:
        ct = ContentType.objects.get_for_model(instance)
        id = instance.pk
        cl = ChangeLog.objects.create(content_type=ct, object_id=id, action=DELETION)
        try:
            k = repr(instance.natural_key())
            DeleteKey.objects.create(changelog=cl, key=k)
        except AttributeError:
            pass

# start logging
from signals import synchro_connect
synchro_connect()
