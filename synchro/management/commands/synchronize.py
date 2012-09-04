from datetime import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand
from django.db import transaction

from synchro.models import Reference, ChangeLog, DeleteKey, options as app_options
from synchro.models import ADDITION, CHANGE, DELETION
from synchro.settings import REMOTE, LOCAL


def get_object_for_this_type_using(self, using, **kwargs):
    return self.model_class()._default_manager.using(using).get(**kwargs)
ContentType.get_object_for_this_type_using = get_object_for_this_type_using


def find_ref(ct, id):
    """
    Retrieves referenced remote object. Also deletes invalid reference.

    Returns (remote, reference) or (None, None).
    """
    try:
        ref = Reference.objects.get(content_type=ct, local_object_id=id)
        try:
            rem = ct.get_object_for_this_type_using(REMOTE, pk=ref.remote_object_id)
            return rem, ref
        except ObjectDoesNotExist:
            ref.delete()
            return None, None
    except Reference.DoesNotExist:
        return None, None


def find_natural(ct, loc, key=None):
    """Tries to find remote object for specified natural key or loc.natural_key."""
    try:
        key = key or loc.natural_key()
        model = ct.model_class()
        return model.objects.db_manager(REMOTE).get_by_natural_key(*key)
    except (AttributeError, ObjectDoesNotExist):
        return None


def is_remote_newer(loc, rem):
    try:
        loc_ct = ContentType.objects.get_for_model(loc)
        rem_ct = ContentType.objects.db_manager(REMOTE).get_for_model(rem)
        loc_time = (ChangeLog.objects.filter(content_type=loc_ct, object_id=loc.pk)
                    .order_by('-date')[0].date)
        rem_time = (ChangeLog.objects.filter(content_type=rem_ct, object_id=rem.pk)
                    .order_by('-date').using(REMOTE)[0].date)
        return rem_time >= loc_time
    except (ObjectDoesNotExist, IndexError):
        return False


def save_with_fks(ct, obj, new_pk):
    """Saves object in REMOTE, ensuring that every of it fk/m2m is present in REMOTE."""
    old_id = obj.pk
    obj._state.db = REMOTE

    fks = (f for f in obj._meta.fields if f.rel)
    for f in fks:
        fk_id = f.value_from_object(obj)
        if fk_id is not None:
            fk_ct = ContentType.objects.get_for_model(f.rel.to)
            rem, _ = ensure_exist(fk_ct, fk_id)
            f.save_form_data(obj, rem)

    _m2m = {}
    for f in obj._meta.many_to_many:
        fk_ct = ContentType.objects.get_for_model(f.rel.to)
        out = []
        for fk_id in f.value_from_object(obj).using(LOCAL).values_list('pk', flat=True):
            rem, _ = ensure_exist(fk_ct, fk_id)
            out.append(rem)
        _m2m[f] = out

    obj.pk = new_pk
    obj.save(using=REMOTE)
    r, n = Reference.objects.get_or_create(content_type=ct, local_object_id=old_id,
                                           defaults={'remote_object_id': obj.pk})
    if not n and r.remote_object_id != obj.pk:
        r.remote_object_id = obj.pk
        r.save()

    for f, out in _m2m.iteritems():
        f.save_form_data(obj, out)


def create_with_fks(ct, obj, pk):
    """Performs create, but firstly disables synchro of some user defined fields (if any)"""
    skip = getattr(obj, 'SYNCHRO_SKIP', ())
    raw = obj.__class__()
    for f in skip:
        setattr(obj, f, getattr(raw, f))
    return save_with_fks(ct, obj, pk)


def change_with_fks(ct, obj, rem):
    """Performs change, but firstly disables synchro of some user defined fields (if any)"""
    skip = getattr(obj, 'SYNCHRO_SKIP', ())
    for f in skip:
        setattr(obj, f, getattr(rem, f))
    return save_with_fks(ct, obj, rem.pk)


def ensure_exist(ct, id):
    """
    Ensures that remote object exists for specified ct/id. If not, create it.
    Returns remote object and reference.
    """
    obj = ct.get_object_for_this_type(pk=id)
    rem, ref = find_ref(ct, obj.pk)
    if rem is not None:
        return rem, ref
    rem = find_natural(ct, obj)
    if rem is not None:
        # maybe create ref?
        return rem, None
    return perform_add(ct, id)


def perform_add(ct, id, log=None):
    obj = ct.get_object_for_this_type(pk=id)
    rem = find_natural(ct, obj)
    if rem is not None:
        if not is_remote_newer(obj, rem):
            change_with_fks(ct, obj, rem)
            rem = obj
    else:
        new_pk = None if obj._meta.has_auto_field else obj.pk
        create_with_fks(ct, obj, new_pk)
        rem = obj
    ref, _ = Reference.objects.get_or_create(content_type=ct, local_object_id=id,
                                             remote_object_id=rem.pk)
    return rem, ref


def perform_chg(ct, id, log=None):
    obj = ct.get_object_for_this_type(pk=id)
    rem, ref = find_ref(ct, obj.pk)
    if rem is not None:
        return change_with_fks(ct, obj, rem)
    rem = find_natural(ct, obj)
    if rem is not None:
        return change_with_fks(ct, obj, rem)
    perform_add(ct, id)


def perform_del(ct, id, log):
    rem, ref = find_ref(ct, id)
    if rem is not None:
        return rem.delete()
    try:
        raw_key = log.deletekey.key
        key = eval(raw_key)
        rem = find_natural(ct, None, key)
        if rem is not None:
            rem.delete()
    except DeleteKey.DoesNotExist:
        pass


ACTIONS = {
    ADDITION: perform_add,
    CHANGE:   perform_chg,
    DELETION: perform_del,
}


class Command(BaseCommand):
    args = ''
    help = '''Perform synchronization.'''

    @transaction.commit_on_success
    @transaction.commit_on_success(using=REMOTE)
    def handle(self, *args, **options):
        since = app_options.last_check
        last_time = datetime.now()
        logs = ChangeLog.objects.filter(date__gt=since).select_related().order_by('date', 'pk')

        # Don't synchronize if object should be added/changed and later deleted;
        to_del = {}
        for log in logs:
            if log.action == DELETION:
                to_del[(log.content_type, log.object_id)] = log.date

        for log in logs:
            last_time = log.date
            del_time = to_del.get((log.content_type, log.object_id))
            if last_time == del_time and log.action == DELETION:
                ACTIONS[log.action](log.content_type, log.object_id, log)
                # delete record so that next actions with the same time can be performed
                del to_del[(log.content_type, log.object_id)]
            if del_time is None or last_time > del_time:
                ACTIONS[log.action](log.content_type, log.object_id, log)

        if len(logs):
            app_options.last_check = last_time
            msg = 'Synchronization performed successfully.'
        else:
            msg = 'No changes since last synchronization.'

        if options['verbosity'] > 0:
            self.stdout.write('%s\n' % msg)
