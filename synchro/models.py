from __future__ import absolute_import
import django
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.utils import timezone
import dbsettings
import six


M2M_CHANGE = 4

ACTIONS = (
    (ADDITION, 'Add'),
    (CHANGE, 'Change'),
    (DELETION, 'Delete'),
    (M2M_CHANGE, 'M2m Change'),
)


class SynchroSettings(dbsettings.Group):
    last_check = dbsettings.DateTimeValue('Last synchronization', default=timezone.now)
options = SynchroSettings()


class Reference(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    local_object_id = models.CharField(max_length=256)
    remote_object_id = models.CharField(max_length=256)

    class Meta:
        unique_together = ('content_type', 'local_object_id')


class ChangeLog(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=256)
    object = GenericForeignKey()
    date = models.DateTimeField(auto_now=True)
    action = models.PositiveSmallIntegerField(choices=ACTIONS)

    def __unicode__(self):
        return u'ChangeLog for %s (%s)' % (six.text_type(self.object), self.get_action_display())


class DeleteKey(models.Model):
    changelog = models.OneToOneField(ChangeLog, on_delete=models.CASCADE)
    key = models.CharField(max_length=256)
