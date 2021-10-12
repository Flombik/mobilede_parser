from collections import defaultdict

from django.db import models
from furl import furl


class ParametersValidationError(Exception):
    def __init__(self, message, *args):
        super().__init__(message, *args)


class QueryParametersModelBase(models.Model):
    class Meta:
        abstract = True

    class QueryParametersQuerySet(models.QuerySet):
        def filter(self, *args, **kwargs):
            url = kwargs.pop('url', None)
            if url is not None and 'parameters' not in kwargs:
                params = self.model.parse_and_validate_url(url)
                kwargs['parameters'] = params

            return super().filter(*args, **kwargs)

    objects = QueryParametersQuerySet.as_manager()

    root_url = ''
    single_value_fields = ()
    multiple_value_fields = ()

    overriding_params = {}
    excluding_params = ()

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

    @classmethod
    def _validate_params(cls, params: dict):
        for key, value in params.items():
            if key not in cls.single_value_fields + cls.multiple_value_fields:
                raise ParametersValidationError(f'Parameter "{key}" is not allowed.')
            if key in cls.single_value_fields and type(value) is list:
                raise ParametersValidationError(f'Value of parameter "{key}" must be single.')

    @classmethod
    def parse_and_validate_url(cls, url):
        url, params = cls._parse_url(url)
        if furl(cls.root_url).origin != url.origin:
            raise ParametersValidationError('URL origin must match root URL.')
        cls._validate_params(params)
        for param in cls.excluding_params + tuple(cls.overriding_params.keys()):
            params.pop(param, None)
        return params

    @property
    def url(self) -> str:
        params = self.parameters | self.overriding_params
        for param in self.excluding_params:
            params.pop(param, None)
        url = furl(self.root_url, query_params=params)
        return url.url

    @url.setter
    def url(self, url):
        params = self.parse_and_validate_url(url)
        self.parameters = params
