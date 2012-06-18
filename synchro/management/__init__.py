import datetime

from dbsettings.utils import set_defaults
from synchro import models


set_defaults(models,
     ('', 'last_check', datetime.datetime.now()),
)
