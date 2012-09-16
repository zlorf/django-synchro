from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.db import models
import dbsettings

#noinspection PyUnresolvedReferences
import settings  # in order to validate

M2M_CHANGE = 4

ACTIONS = (
    (ADDITION, 'Add'),
    (CHANGE, 'Change'),
    (DELETION, 'Delete'),
    (M2M_CHANGE, 'M2m Change'),
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


def delete_redundant_change(cl):
    """
    Takes ChangeLog instance as argument and if previous ChangeLog for the same object
    has the same type, deletes it.
    It ensures that if several object's changes were made one-by-one, only one ChangeLog is stored
    afterwards.
    """
    cls = (ChangeLog.objects.filter(content_type=cl.content_type, object_id=cl.object_id)
           .exclude(pk=cl.pk).order_by('-date', '-pk'))
    if len(cls) > 0 and cls[0].action == cl.action:
        cls[0].delete()


def save_changelog_add_chg(sender, instance, created, using, **kwargs):
    if sender in settings.MODELS and using == settings.LOCAL:
        if created:
            ChangeLog.objects.create(object=instance, action=ADDITION)
        else:
            cl = ChangeLog.objects.create(object=instance, action=CHANGE)
            delete_redundant_change(cl)
    elif sender in settings.INTER_MODELS and using == settings.LOCAL:
        rel = settings.INTER_MODELS[sender]
        # It doesn't matter if we select forward or reverse object here; arbitrary choose forward
        real_instance = getattr(instance, rel.field.m2m_field_name())
        cl = ChangeLog.objects.create(object=real_instance, action=M2M_CHANGE)
        delete_redundant_change(cl)


def save_changelog_del(sender, instance, using, **kwargs):
    if sender in settings.MODELS and using == settings.LOCAL:
        cl = ChangeLog.objects.create(object=instance, action=DELETION)
        try:
            k = repr(instance.natural_key())
            DeleteKey.objects.create(changelog=cl, key=k)
        except AttributeError:
            pass


def save_changelog_m2m(sender, instance, model, using, action, **kwargs):
    if ((model in settings.MODELS or instance.__class__ in settings.MODELS)
            and action.startswith('post') and using == settings.LOCAL):
        cl = ChangeLog.objects.create(object=instance, action=M2M_CHANGE)
        delete_redundant_change(cl)


# start logging
from signals import synchro_connect
synchro_connect()
