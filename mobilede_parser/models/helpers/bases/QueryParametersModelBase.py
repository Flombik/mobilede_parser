from collections import defaultdict

from django.db import models
from furl import furl


class ParametersValidationError(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)


class QueryParametersModelBase(models.Model):
    class Meta:
        abstract = True

    root_url = ''
    single_value_fields = ()
    multiple_value_fields = ()

    overriding_params = {}
    excluding_params = ()

    @property
    def fields(self):
        return self.single_value_fields + self.multiple_value_fields

    parameters = models.JSONField(default=dict)

    @staticmethod
    def _parse_url(url) -> tuple[furl, dict]:
        url = furl(url)
        params = defaultdict(list)
        for key, value in url.args.iterallitems():
            if value is not None:
                params[key].append(value)
            else:
                params.setdefault('key')
        params = {
            key: None if not value else value[0] if len(value) == 1 else value
            for key, value in params.items()
        }
        return url, params

    def _validate_params(self, params: dict):
        for key, value in params.items():
            if key not in self.fields:
                raise ParametersValidationError(f'Parameter "{key}" is not allowed.')
            if key in self.single_value_fields and type(value) is list:
                raise ParametersValidationError(f'Value of parameter "{key}" must be single.')

    @property
    def url(self) -> str:
        params = self.parameters | self.overriding_params
        for param in self.excluding_params:
            params.pop(param, None)
        url = furl(self.root_url, query_params=params)
        return url.url

    @url.setter
    def url(self, url):
        url, params = self._parse_url(url)
        if furl(self.root_url).origin != url.origin:
            raise ParametersValidationError('URL origin must match root URL.')
        self._validate_params(params)
        self.parameters = params
