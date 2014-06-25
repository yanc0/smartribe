from django.db import models


class Community(models.Model):

    name = models.CharField(max_length=50,
                            unique=True)

    description = models.TextField(max_length=180)

    banner = models.ImageField(blank=True,
                               null=True)

    logo = models.ImageField(blank=True,
                             null=True)

    creation_date = models.DateField(auto_now_add=True)

    auto_accept_member = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'community'
        verbose_name_plural = 'communities'
        app_label = 'core'
