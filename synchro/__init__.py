from datetime import datetime

from signals import DisableSynchroLog, disable_synchro_log
from utility import natural_manager

def reset_synchro():
    from models import ChangeLog, Reference, options
    options.last_check = datetime.now()
    ChangeLog.objects.all().delete()
    Reference.objects.all().delete()
