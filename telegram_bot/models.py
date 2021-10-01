from django.db import models


# Create your models here.
class Persistence(models.Model):
    data = models.JSONField(default=dict)
