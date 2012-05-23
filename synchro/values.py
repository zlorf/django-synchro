import datetime

from django import forms
from django.utils import formats

from dbsettings.values import Value


class DateValue(Value):
    field = forms.DateField
    formats_source = 'DATE_INPUT_FORMATS'

    @property
    def _formats(self):
        return formats.get_format(self.formats_source)

    def _parse_format(self, value):
        for format in self._formats:
            try:
                return datetime.datetime.strptime(value, format)
            except ValueError:
                continue
        return None

    def get_db_prep_save(self, value):
        return value.strftime(self._formats[0])

    def to_python(self, value):
        if isinstance(value, datetime.datetime):
            return value.date()
        elif isinstance(value, datetime.date):
            return value
        res = self._parse_format(value)
        if res is not None:
            return res.date()
        return res

class DateTimeValue(DateValue):
    field = forms.DateTimeField
    formats_source = 'DATETIME_INPUT_FORMATS'

    def to_python(self, value):
        if isinstance(value, datetime.datetime):
            return value
        return self._parse_format(value)
