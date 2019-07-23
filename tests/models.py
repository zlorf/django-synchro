from django.db import models

from django.dispatch import receiver
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import F

from synchro.signals import DisableSynchroLog, disable_synchro_log
from synchro.utility import NaturalManager, reset_synchro, NaturalKeyModel


class TestModel(models.Model):
    name = models.CharField(max_length=10)
    cash = models.IntegerField(default=0)


class PkModelWithSkip(models.Model):
    name = models.CharField(max_length=10, primary_key=True)
    cash = models.IntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    SYNCHRO_SKIP = ('visits',)


class ModelWithFK(models.Model):
    name = models.CharField(max_length=10)
    visits = models.PositiveIntegerField(default=0)
    link = models.ForeignKey(PkModelWithSkip, related_name='links', on_delete=models.CASCADE)


@receiver(pre_save, sender=ModelWithFK)
def save_prev(sender, instance, **kwargs):
    """Save object's previous state (before save)."""
    try:
        instance._prev = sender.objects.db_manager(instance._state.db).get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._prev = None


@receiver(post_save, sender=ModelWithFK)
@disable_synchro_log
def update_visits(sender, instance, created, **kwargs):
    """Update parent visits."""
    if not created:
        # Side note: in the statement below it should be instance._prev.link in case of link change,
        # but it requires some refreshing from database (since instance._prev.link and instance.link
        # are two different instances of the same object). For this test
        instance.link.visits -= instance._prev.visits
        instance.link.save()
    instance.link.visits += instance.visits
    instance.link.save()


class CustomManager(models.Manager):
    def foo(self):
        return 'bar'

    def none(self):  # Overrides Manager method
        return 'Not a single object!'


class MyNaturalManager(NaturalManager, CustomManager):
    fields = ('name',)


class ModelWithKey(NaturalKeyModel):
    name = models.CharField(max_length=10)
    cash = models.IntegerField(default=0)
    visits = models.PositiveIntegerField(default=0)
    SYNCHRO_SKIP = ('visits',)
    _natural_key = ('name',)

    objects = CustomManager()
    another_objects = MyNaturalManager()


class ModelWithFKtoKey(models.Model):
    name = models.CharField(max_length=10)
    link = models.ForeignKey(ModelWithKey, related_name='links', on_delete=models.CASCADE)


class M2mModelWithKey(models.Model):
    foo = models.IntegerField(default=1)
    objects = NaturalManager('foo')

    def natural_key(self):
        return self.foo,


class M2mAnother(models.Model):
    bar = models.IntegerField(default=1)
    m2m = models.ManyToManyField('M2mModelWithKey', related_name='r_m2m')


class M2mModelWithInter(models.Model):
    bar = models.IntegerField(default=1)
    m2m = models.ManyToManyField('M2mModelWithKey', related_name='r_m2m_i',
                                 through='M2mIntermediate')


class M2mNotExplicitlySynced(models.Model):
    # This model is not listed in SYNCHRO_MODELS
    foo = models.IntegerField(default=1)


class M2mIntermediate(models.Model):
    with_key = models.ForeignKey(M2mModelWithKey, on_delete=models.CASCADE)
    with_inter = models.ForeignKey(M2mModelWithInter, on_delete=models.CASCADE)
    # To get everything worse, use another FK here, in order to test intermediate sync.
    extra = models.ForeignKey(M2mNotExplicitlySynced, on_delete=models.CASCADE)
    cash = models.IntegerField()


class M2mSelf(models.Model):
    foo = models.IntegerField(default=1)
    m2m = models.ManyToManyField('self')


class A(models.Model):
    foo = models.IntegerField(default=1)
    bar = models.IntegerField(default=1)


class X(models.Model):
    name = models.CharField(max_length=10)


def update_bar_bad(sender, using, **kwargs):
    a = A.objects.db_manager(using).all()[0]
    a.bar += 1
    a.save()


@disable_synchro_log
def update_bar_good_dis(sender, using, **kwargs):
    a = A.objects.db_manager(using).all()[0]
    a.bar += 1
    a.save()


def update_bar_good_upd(sender, using, **kwargs):
    A.objects.db_manager(using).update(bar=F('bar') + 1)  # update don't emmit signals
