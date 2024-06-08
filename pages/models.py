from django.db import models


class PageContent(models.Model):
    page_name = models.CharField(max_length=50, unique=True)
    content = models.TextField()
