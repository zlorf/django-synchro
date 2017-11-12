import datetime

from django import VERSION
from django.conf import settings
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.core.management import call_command, CommandError
from django.core.urlresolvers import reverse
from django.db import models
from django.db.models import F
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from django.test import TestCase
from django.test.utils import override_settings
try:
    from unittest.case import skipUnless
except ImportError:
    from django.utils.unittest.case import skipUnless

from models import ChangeLog
import settings as synchro_settings
from signals import DisableSynchroLog, disable_synchro_log
from utility import NaturalManager, reset_synchro, NaturalKeyModel

from django.contrib.auth import get_user_model
User = get_user_model()

def user_model_quite_standard():
    "Check if installed User object is not too custom for the tests to instantiate it."
    from django.contrib.auth.models import User as StandardUser
    if (User.USERNAME_FIELD == StandardUser.USERNAME_FIELD and
            User.REQUIRED_FIELDS == StandardUser.REQUIRED_FIELDS):
        return True
    return False

LOCAL = 'default'
REMOTE = settings.SYNCHRO_REMOTE
# List of test models
SETTINGS = {
    'SYNCHRO_MODELS': (
        ('synchro', 'testmodel', 'PkModelWithSkip', 'ModelWithKey', 'ModelWithFK', 'A', 'X',
         'M2mModelWithKey', 'M2mAnother', 'M2mModelWithInter', 'M2mSelf', 'ModelWithFKtoKey'),
    ),
    'ROOT_URLCONF': 'synchro.test_urls',
}


def contrib_apps(*apps):
    """Check if all listed apps are installed."""
    for app in apps:
        if 'django.contrib.%s' % app not in settings.INSTALLED_APPS:
            return False
    return True


# #### Test models ################################


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
    link = models.ForeignKey(PkModelWithSkip, related_name='links')


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
    link = models.ForeignKey(ModelWithKey, related_name='links')


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
    with_key = models.ForeignKey(M2mModelWithKey)
    with_inter = models.ForeignKey(M2mModelWithInter)
    # To get everything worse, use another FK here, in order to test intermediate sync.
    extra = models.ForeignKey(M2mNotExplicitlySynced)
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


# #### Tests themselves ###########################


@override_settings(**SETTINGS)
class SynchroTests(TestCase):
    multi_db = True

    @classmethod
    def setUpClass(cls):
        """Update SYNCHRO_MODELS and reload them"""
        super(SynchroTests, cls).setUpClass()
        if VERSION < (1, 8):
            with override_settings(**SETTINGS):
                reload(synchro_settings)
        else:
            reload(synchro_settings)

    @classmethod
    def tearDownClass(cls):
        """Clean up after yourself: restore the previous SYNCHRO_MODELS"""
        super(SynchroTests, cls).tearDownClass()
        reload(synchro_settings)

    def _assertDbCount(self, db, num, cls):
        self.assertEqual(num, cls.objects.db_manager(db).count())

    def assertLocalCount(self, num, cls):
        self._assertDbCount(LOCAL, num, cls)

    def assertRemoteCount(self, num, cls):
        self._assertDbCount(REMOTE, num, cls)

    def synchronize(self, **kwargs):
        call_command('synchronize', verbosity=0, **kwargs)

    def wait(self):
        """
        Since tests are run too fast, we need to wait for a moment, so that some ChangeLog objects
        could be considered "old" and not synchronized again.
        Waiting one second every time this method is called would lengthen tests - so instead we
        simulate time shift.
        """
        ChangeLog.objects.update(date=F('date') - datetime.timedelta(seconds=1))
        ChangeLog.objects.db_manager(REMOTE).update(date=F('date') - datetime.timedelta(seconds=1))

    def reset(self):
        reset_synchro()

    def assertNoActionOnSynchronize(self, sender, save=True, delete=True):
        def fail(**kwargs):
            self.fail('Signal caught - action performed.')
        if save:
            post_save.connect(fail, sender=sender)
        if delete:
            post_delete.connect(fail, sender=sender)
        self.synchronize()
        post_save.disconnect(fail, sender=sender)
        post_delete.disconnect(fail, sender=sender)


class SimpleSynchroTests(SynchroTests):
    """Cover basic functionality."""

    def test_settings(self):
        """Check if test SYNCHRO_MODELS is loaded."""
        self.assertIn(TestModel, synchro_settings.MODELS)
        self.assertIn(PkModelWithSkip, synchro_settings.MODELS)
        self.assertNotIn(ChangeLog, synchro_settings.MODELS)

    def test_app_paths(self):
        """Check if app in SYNCHRO_MODELS can be stated in any way."""
        from django.contrib.auth.models import Group
        self.assertNotIn(Group, synchro_settings.MODELS)

        INSTALLED_APPS = settings.INSTALLED_APPS
        if 'django.contrib.auth' not in INSTALLED_APPS:
            INSTALLED_APPS = INSTALLED_APPS + ('django.contrib.auth',)
        with override_settings(INSTALLED_APPS=INSTALLED_APPS):
            # fully qualified path
            with override_settings(SYNCHRO_MODELS=('django.contrib.auth',)):
                reload(synchro_settings)
                self.assertIn(Group, synchro_settings.MODELS)
            # app label
            with override_settings(SYNCHRO_MODELS=('auth',)):
                reload(synchro_settings)
                self.assertIn(Group, synchro_settings.MODELS)

        # Restore previous state
        reload(synchro_settings)
        self.assertNotIn(Group, synchro_settings.MODELS)

    def test_settings_with_invalid_remote(self):
        """Check if specifying invalid remote results in exception."""
        with override_settings(SYNCHRO_REMOTE='invalid'):
            with self.assertRaises(ImproperlyConfigured):
                reload(synchro_settings)
        # Restore previous state
        reload(synchro_settings)
        self.assertEqual(REMOTE, synchro_settings.REMOTE)

    def test_settings_without_remote(self):
        """Check if lack of REMOTE in settings cause synchronization disablement."""
        import synchro.management.commands.synchronize
        try:
            with override_settings(SYNCHRO_REMOTE=None):
                reload(synchro_settings)
                reload(synchro.management.commands.synchronize)
                self.assertIsNone(synchro_settings.REMOTE)
                self.assertLocalCount(0, ChangeLog)
                TestModel.objects.create(name='James', cash=7)
                self.assertLocalCount(1, TestModel)
                # ChangeLog created successfully despite lack of REMOTE
                self.assertLocalCount(1, ChangeLog)

                self.assertRaises(CommandError, self.synchronize)

        finally:
            # Restore previous state
            reload(synchro_settings)
            reload(synchro.management.commands.synchronize)
            self.assertEqual(REMOTE, synchro_settings.REMOTE)

    def test_simple_synchro(self):
        """Check object creation and checkpoint storage."""
        prev = datetime.datetime.now()
        a = TestModel.objects.create(name='James', cash=7)
        self.assertLocalCount(1, TestModel)
        self.assertRemoteCount(0, TestModel)
        self.synchronize()
        self.assertLocalCount(1, TestModel)
        self.assertRemoteCount(1, TestModel)
        b = TestModel.objects.db_manager(REMOTE).all()[0]
        self.assertFalse(a is b)
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.cash, b.cash)
        from synchro.models import options
        self.assertTrue(options.last_check >= prev.replace(microsecond=0))

    def test_auto_pk(self):
        """
        Test if auto pk is *not* overwritten.
        Although local object has the same pk as remote one, new object will be created,
        because pk is automatic.
        """
        some = TestModel.objects.db_manager(REMOTE).create(name='Remote James', cash=77)
        a = TestModel.objects.create(name='James', cash=7)
        self.assertEquals(a.pk, some.pk)
        self.synchronize()
        self.assertLocalCount(1, TestModel)
        self.assertRemoteCount(2, TestModel)
        self.assertTrue(TestModel.objects.db_manager(REMOTE).get(name='James'))
        self.assertTrue(TestModel.objects.db_manager(REMOTE).get(name='Remote James'))

    def test_not_auto_pk(self):
        """
        Test if explicit pk *is overwritten*.
        If local object has the same pk as remote one, remote object will be completely overwritten.
        """
        some = PkModelWithSkip.objects.db_manager(REMOTE).create(name='James', cash=77, visits=5)
        a = PkModelWithSkip.objects.create(name='James', cash=7, visits=42)
        self.assertEquals(a.pk, some.pk)
        self.synchronize()
        self.assertLocalCount(1, PkModelWithSkip)
        self.assertRemoteCount(1, PkModelWithSkip)
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(7, b.cash)
        # Because whole object is copied, skipping use default value.
        self.assertEqual(0, b.visits)

    def test_change(self):
        """Test simple change"""
        a = TestModel.objects.create(name='James', cash=7)
        self.synchronize()
        self.wait()
        a.name = 'Bond'
        a.save()
        self.synchronize()
        b = TestModel.objects.db_manager(REMOTE).get(cash=7)
        self.assertEqual(a.name, b.name)

    def test_skipping_add(self):
        """Test if field is skipped during creation - that is, cleared."""
        PkModelWithSkip.objects.create(name='James', cash=7, visits=42)
        self.synchronize()
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(7, b.cash)
        self.assertEqual(0, b.visits)  # Skipping use default value when creating

    def test_skipping_change(self):
        """Test if field is skipped."""
        a = PkModelWithSkip.objects.create(name='James', cash=7)
        self.synchronize()
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        b.visits = 42
        b.save()
        self.wait()
        a.cash = 77
        a.save()
        self.synchronize()
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(a.cash, b.cash)
        self.assertEqual(42, b.visits)

    def test_deletion(self):
        """Test deletion."""
        a = TestModel.objects.create(name='James', cash=7)
        self.synchronize()
        self.assertRemoteCount(1, TestModel)
        self.wait()
        a.delete()
        self.synchronize()
        self.assertRemoteCount(0, TestModel)

    def test_untracked_deletion(self):
        """Test if deletion is not performed on lack of Reference and key."""
        TestModel.objects.db_manager(REMOTE).create(name='James', cash=7)
        a = TestModel.objects.create(name='James', cash=7)
        self.reset()
        a.delete()
        self.synchronize()
        self.assertLocalCount(0, TestModel)
        self.assertRemoteCount(1, TestModel)

    def test_add_del(self):
        """Test if no unnecessary action is performed if added and deleted."""
        a = TestModel.objects.create(name='James')
        a.delete()
        self.assertNoActionOnSynchronize(TestModel)
        self.assertRemoteCount(0, TestModel)

    def test_chg_del(self):
        """Test if no unnecessary action is performed if changed and deleted."""
        a = TestModel.objects.create(name='James', cash=7)
        self.synchronize()
        self.wait()
        a.name = 'Bond'
        a.save()
        a.delete()
        self.assertNoActionOnSynchronize(TestModel, delete=False)
        self.assertRemoteCount(0, TestModel)

    def test_add_chg_del_add_chg(self):
        """Combo."""
        a = TestModel.objects.create(name='James', cash=7)
        a.name = 'Bond'
        a.save()
        a.delete()
        a = TestModel.objects.create(name='Vimes', cash=7)
        a.cash = 77
        a.save()
        self.synchronize()
        self.assertRemoteCount(1, TestModel)
        b = TestModel.objects.db_manager(REMOTE).get(name='Vimes')
        self.assertEqual(a.cash, b.cash)

    def test_reference(self):
        """Test if object once synchronized is linked with remote instance."""
        some = TestModel.objects.db_manager(REMOTE).create(name='Remote James', cash=77)
        a = TestModel.objects.create(name='James', cash=7)
        self.assertEquals(a.pk, some.pk)
        self.synchronize()
        self.assertRemoteCount(2, TestModel)
        b = TestModel.objects.db_manager(REMOTE).get(name='James')
        self.assertNotEquals(a.pk, b.pk)
        b.name = 'Bond'
        b.save()  # This change will be discarded
        self.wait()
        a.cash = 42
        a.save()
        self.synchronize()
        b = TestModel.objects.db_manager(REMOTE).get(pk=b.pk)
        self.assertEqual(a.name, b.name)
        self.assertEqual(a.cash, b.cash)

    def test_reference2(self):
        """Test if reference is created for model found with natural key."""
        ModelWithKey.objects.db_manager(REMOTE).create(name='James')
        loc = ModelWithKey.objects.create(name='James')
        self.wait()
        ModelWithFKtoKey.objects.create(name='Test', link=loc)
        self.synchronize()
        self.assertRemoteCount(1, ModelWithFKtoKey)
        self.assertRemoteCount(1, ModelWithKey)

    def test_time_comparing(self):
        """Test if synchronization is not performed if REMOTE object is newer."""
        a = TestModel.objects.create(name="James", cash=7)
        self.synchronize()
        self.assertRemoteCount(1, TestModel)
        self.wait()
        a.cash = 42  # local change
        a.save()
        self.wait()
        b = TestModel.objects.db_manager(REMOTE).get(name="James")
        b.cash = 77  # remote change, done later
        b.save()
        self.assertNoActionOnSynchronize(TestModel)
        self.assertRemoteCount(1, TestModel)
        b = TestModel.objects.db_manager(REMOTE).get(name="James")
        self.assertEqual(77, b.cash)  # remote object hasn't changed

    @skipUnless(contrib_apps('admin', 'auth', 'sessions'),
                'admin, auth or sessions not in INSTALLED_APPS')
    @skipUnless(user_model_quite_standard(), 'Too custom User model')
    def test_admin(self):
        """Test if synchronization can be performed via admin interface."""
        path = reverse('synchro')
        user = User._default_manager.create_user('admin', 'mail', 'admin')
        self.client.login(username='admin', password='admin')
        # test if staff status is required
        response = self.client.get(path)
        try:
            self.assertTemplateUsed(response, 'admin/login.html')
        except AssertionError:  # Django >= 1.7
            self.assertIn('location', response._headers)
            self.assertIn('/admin/login/', response._headers['location'][1])
        user.is_staff = True
        user.save()
        # superuser
        self.assertTemplateUsed(self.client.get(path), 'synchro.html')
        # actual synchronization
        self.reset()
        TestModel.objects.create(name='James', cash=7)
        self.assertRemoteCount(0, TestModel)
        self.client.post(path, {'synchro': True})  # button clicked
        self.assertRemoteCount(1, TestModel)
        # resetting
        self.assertGreater(ChangeLog.objects.count(), 0)
        self.client.post(path, {'reset': True})  # button clicked
        self.assertEqual(ChangeLog.objects.count(), 0)

    def test_translation(self):
        """Test if texts are translated."""
        from django.utils.translation import override
        from django.utils.encoding import force_unicode
        from synchro.core import call_synchronize
        languages = ('en', 'pl', 'de', 'es', 'fr')
        messages = set()
        for lang in languages:
            with override(lang):
                messages.add(force_unicode(call_synchronize()))
        self.assertEqual(len(messages), len(languages), 'Some language is missing.')


class AdvancedSynchroTests(SynchroTests):
    """Cover additional features."""

    def test_manager_class(self):
        """Test if NaturalManager works."""
        self.assertIsInstance(ModelWithKey.objects, NaturalManager)
        self.assertIsInstance(ModelWithKey.another_objects, NaturalManager)
        # Test if it subclasses user manager as well
        self.assertIsInstance(ModelWithKey.objects, CustomManager)
        self.assertIsInstance(ModelWithKey.another_objects, CustomManager)
        self.assertEqual('bar', ModelWithKey.objects.foo())
        self.assertEqual('bar', ModelWithKey.another_objects.foo())
        # Check proper MRO: NaturalManager, user manager, Manager
        self.assertTrue(hasattr(ModelWithKey.objects, 'get_by_natural_key'))
        self.assertTrue(hasattr(ModelWithKey.another_objects, 'get_by_natural_key'))
        self.assertEqual('Not a single object!', ModelWithKey.objects.none())
        self.assertEqual('Not a single object!', ModelWithKey.another_objects.none())
        self.assertSequenceEqual([], ModelWithKey.objects.all())
        self.assertSequenceEqual([], ModelWithKey.another_objects.all())

        # Test get_by_natural_key
        obj = ModelWithKey.objects.create(name='James')
        self.assertEqual(obj.pk, ModelWithKey.objects.get_by_natural_key('James').pk)
        self.assertEqual(obj.pk, ModelWithKey.another_objects.get_by_natural_key('James').pk)

        # Test instantiating (DJango #13313: manager must be instantiable without arguments)
        try:
            ModelWithKey.objects.__class__()
            ModelWithKey.another_objects.__class__()
        except TypeError:
            self.fail('Cannot instantiate.')

        # Test if class checking occurs
        def wrong():
            class BadManager:
                pass

            class X(models.Model):
                x = models.IntegerField()
                objects = NaturalManager('x', manager=BadManager)
        self.assertRaises(ValidationError, wrong)  # User manager must subclass Manager

        # Test if manager without fields raises exception
        def wrong2():
            class X(models.Model):
                x = models.IntegerField()
                objects = NaturalManager()
        self.assertRaises(AssertionError, wrong2)

    def test_natural_key(self):
        """
        Test if natural key works.
        If local object has the same key as remote one, remote object will be updated.
        """
        b = ModelWithKey.objects.db_manager(REMOTE).create(name='James', cash=77, visits=5)
        a = ModelWithKey.objects.create(name='James', cash=7, visits=42, pk=2)
        self.assertNotEquals(a.pk, b.pk)
        self.synchronize()
        self.assertLocalCount(1, ModelWithKey)
        self.assertRemoteCount(1, ModelWithKey)
        remote = ModelWithKey.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(7, remote.cash)
        # Because remote object is found, skipping use remote value (not default).
        self.assertEqual(5, remote.visits)

    def test_natural_key_deletion(self):
        """
        Test if natural key works on deletion.
        When no Reference exist, delete object matching natural key.
        """
        ModelWithKey.objects.db_manager(REMOTE).create(name='James', cash=77, visits=5)
        a = ModelWithKey.objects.create(name='James', cash=7, visits=42, pk=2)
        self.reset()
        a.delete()
        self.synchronize()
        self.assertLocalCount(0, ModelWithKey)
        self.assertRemoteCount(0, ModelWithKey)

    def test_foreign_keys(self):
        """Test if foreign keys are synchronized."""
        a = PkModelWithSkip.objects.create(name='James')
        self.reset()  # Even if parent model is not recorded!
        ModelWithFK.objects.create(name='1', link=a)
        ModelWithFK.objects.create(name='2', link=a)
        self.synchronize()
        self.assertRemoteCount(1, PkModelWithSkip)
        self.assertRemoteCount(2, ModelWithFK)
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(2, b.links.count())
        # Check if all submodels belong to remote db
        self.assertTrue(all(map(lambda x: x._state.db == REMOTE, b.links.all())))

    def test_disabling(self):
        """Test if logging can be disabled."""
        # with context
        with DisableSynchroLog():
            TestModel.objects.create(name='James')
        self.synchronize()
        self.assertLocalCount(1, TestModel)
        self.assertRemoteCount(0, TestModel)

        # with decorator
        @disable_synchro_log
        def create():
            PkModelWithSkip.objects.create(name='James')
        create()
        self.synchronize()
        self.assertLocalCount(1, PkModelWithSkip)
        self.assertRemoteCount(0, PkModelWithSkip)


class SignalSynchroTests(SynchroTests):
    """Cover signals tests."""

    def test_signals_and_skip(self):
        """Some signal case from real life."""
        a = PkModelWithSkip.objects.create(name='James', cash=7)
        self.synchronize()
        self.wait()
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        b.cash = 77  # some remote changes
        b.visits = 10
        b.save()
        self.assertEqual(0, a.visits)
        self.assertEqual(10, b.visits)
        # Adding some submodels
        self.wait()
        ModelWithFK.objects.create(name='1', link=a, visits=30)
        ModelWithFK.objects.create(name='2', link=a, visits=2)
        self.synchronize()
        self.assertRemoteCount(1, PkModelWithSkip)
        a = PkModelWithSkip.objects.get(name='James')
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(32, a.visits)
        self.assertEqual(42, b.visits)
        self.assertEqual(77, b.cash)  # No change in cash
        # Change
        self.wait()
        m2 = ModelWithFK.objects.get(name='2')
        m2.visits = 37
        m2.save()
        self.synchronize()
        a = PkModelWithSkip.objects.get(name='James')
        b = PkModelWithSkip.objects.db_manager(REMOTE).get(name='James')
        self.assertEqual(67, a.visits)
        self.assertEqual(77, b.visits)
        self.assertEqual(77, b.cash)  # Still no change in cash

    def _test_signals_scenario(self, handler, expected):
        """Scenario from README."""
        A.objects.create()
        self.synchronize()
        b = A.objects.db_manager(REMOTE).all()[0]
        b.foo = 42
        b.save()
        self.wait()
        post_save.connect(handler, sender=X, dispatch_uid='update_bar')
        X.objects.create(name='X')
        self.synchronize()
        a = A.objects.all()[0]
        b = A.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(2, a.bar)  # handler was invoked
        self.assertEqual(2, b.bar)  # handler was invoked
        self.assertEqual(1, a.foo)
        self.assertEqual(expected, b.foo)
        post_save.disconnect(sender=X, dispatch_uid='update_bar')

    def test_signals_bad_scenario(self):
        """Demonstrate bad scenario from README."""
        self._test_signals_scenario(update_bar_bad, 1)  # BAD RESULT

    def test_signals_good_scenario(self):
        """Demonstrate solution for scenario from README (disable log)."""
        self._test_signals_scenario(update_bar_good_dis, 42)  # GOOD RESULT

    def test_signals_alternative_good_scenario(self):
        """Demonstrate solution for scenario from README (use update)."""
        self._test_signals_scenario(update_bar_good_upd, 42)  # GOOD RESULT


class M2MSynchroTests(SynchroTests):
    """Cover many2many relations tests."""

    def test_natural_manager(self):
        """Test if natural manager can be instantiated when using M2M."""
        test = M2mModelWithKey.objects.create()
        obj = M2mAnother.objects.create()
        obj.m2m.add(test)  # this would fail if NaturalManager could not be instantiated
        self.assertEqual(test.pk, obj.m2m.get_by_natural_key(1).pk)

    def test_simple_m2m(self):
        """Test if m2m field is synced properly."""
        test = M2mModelWithKey.objects.create()
        a = M2mAnother.objects.create()

        # add
        a.m2m.add(test)
        self.synchronize()
        self.assertRemoteCount(1, M2mAnother)
        self.assertRemoteCount(1, M2mModelWithKey)
        b = M2mAnother.objects.db_manager(REMOTE).all()[0]
        k = M2mModelWithKey.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(1, k.r_m2m.count())
        b_k = b.m2m.all()[0]
        self.assertEqual(b_k.pk, k.pk)
        self.assertEqual(b_k.foo, k.foo)

        # clear
        self.wait()
        a.m2m.clear()
        self.synchronize()
        self.assertEqual(0, b.m2m.count())
        self.assertEqual(0, k.r_m2m.count())

        # reverse add
        self.wait()
        a2 = M2mAnother.objects.create(bar=2)
        test.r_m2m.add(a, a2)
        self.synchronize()
        self.assertRemoteCount(2, M2mAnother)
        self.assertRemoteCount(1, M2mModelWithKey)
        b2 = M2mAnother.objects.db_manager(REMOTE).filter(bar=2)[0]
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(1, b2.m2m.count())
        self.assertEqual(2, k.r_m2m.count())

        # reverse remove
        self.wait()
        test.r_m2m.remove(a)
        self.synchronize()
        self.assertRemoteCount(2, M2mAnother)
        self.assertRemoteCount(1, M2mModelWithKey)
        self.assertEqual(0, b.m2m.count())
        self.assertEqual(1, b2.m2m.count())
        self.assertEqual(1, k.r_m2m.count())

        # reverse clear
        self.wait()
        test.r_m2m.clear()
        self.synchronize()
        self.assertRemoteCount(2, M2mAnother)
        self.assertRemoteCount(1, M2mModelWithKey)
        self.assertEqual(0, b.m2m.count())
        self.assertEqual(0, b2.m2m.count())
        self.assertEqual(0, k.r_m2m.count())

    def test_intermediary_m2m(self):
        """Test if m2m field with explicit intermediary is synced properly."""
        test = M2mNotExplicitlySynced.objects.create(foo=77)
        key = M2mModelWithKey.objects.create()
        a = M2mModelWithInter.objects.create()
        M2mIntermediate.objects.create(with_key=key, with_inter=a, cash=42, extra=test)
        self.assertEqual(1, a.m2m.count())
        self.assertEqual(1, key.r_m2m_i.count())
        self.synchronize()
        self.assertRemoteCount(1, M2mNotExplicitlySynced)
        self.assertRemoteCount(1, M2mModelWithKey)
        self.assertRemoteCount(1, M2mModelWithInter)
        b = M2mModelWithInter.objects.db_manager(REMOTE).all()[0]
        k = M2mModelWithKey.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(1, k.r_m2m_i.count())
        b_k = b.m2m.all()[0]
        self.assertEqual(b_k.pk, k.pk)
        self.assertEqual(b_k.foo, k.foo)
        self.assertEqual(1, b.m2m.all()[0].foo)
        # intermediary
        self.assertRemoteCount(1, M2mIntermediate)
        inter = M2mIntermediate.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(42, inter.cash)
        self.assertEqual(77, inter.extra.foo)  # check if extra FK model get synced

        # changing
        self.wait()
        key2 = M2mModelWithKey.objects.create(foo=42)
        a.m2m.clear()
        M2mIntermediate.objects.create(with_key=key2, with_inter=a, cash=77, extra=test)
        self.synchronize()
        self.assertRemoteCount(1, M2mNotExplicitlySynced)
        self.assertRemoteCount(2, M2mModelWithKey)
        self.assertRemoteCount(1, M2mModelWithInter)
        b = M2mModelWithInter.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(42, b.m2m.all()[0].foo)
        # intermediary
        self.assertRemoteCount(1, M2mIntermediate)
        inter = M2mIntermediate.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(77, inter.cash)

        # intermadiate change
        self.wait()
        inter = M2mIntermediate.objects.all()[0]
        inter.cash = 1
        inter.save()
        self.synchronize()
        # No changes here
        self.assertRemoteCount(1, M2mNotExplicitlySynced)
        self.assertRemoteCount(2, M2mModelWithKey)
        self.assertRemoteCount(1, M2mModelWithInter)
        b = M2mModelWithInter.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(42, b.m2m.all()[0].foo)
        # Still one intermediary
        self.assertRemoteCount(1, M2mIntermediate)
        inter = M2mIntermediate.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(1, inter.cash)

        # Tricky: clear from other side of relation.
        self.wait()
        key2.r_m2m_i.clear()
        self.synchronize()
        b = M2mModelWithInter.objects.db_manager(REMOTE).all()[0]
        self.assertEqual(0, b.m2m.count())
        self.assertRemoteCount(0, M2mIntermediate)

    def test_self_m2m(self):
        """Test if m2m symmetrical field is synced properly."""
        test = M2mSelf.objects.create(foo=42)
        a = M2mSelf.objects.create(foo=1)

        # add
        a.m2m.add(test)
        self.synchronize()
        self.assertRemoteCount(2, M2mSelf)
        b = M2mSelf.objects.db_manager(REMOTE).get(foo=1)
        k = M2mSelf.objects.db_manager(REMOTE).get(foo=42)
        self.assertEqual(1, b.m2m.count())
        self.assertEqual(1, k.m2m.count())
        b_k = b.m2m.all()[0]
        self.assertEqual(b_k.pk, k.pk)
        self.assertEqual(b_k.foo, k.foo)

        # clear
        self.wait()
        a.m2m.clear()
        self.synchronize()
        self.assertEqual(0, b.m2m.count())
        self.assertEqual(0, k.m2m.count())
