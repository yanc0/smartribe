from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, related_name='profile')
    GENDER_CHOICES = (
                     ('M', 'Male'),
                     ('F', 'Female'),
                     ('O', 'Other'),
    )
    gender = models.CharField(max_length=2,
                              choices=GENDER_CHOICES,
                              default='O')

    # address

    # phone = models.CharField(max_length=15)

    birthdate = models.DateField(blank=True,
                                 null=True)

    bio = models.TextField(blank=True,
                           null=True)

    photo = models.ImageField(blank=True,
                              null=True)

    class Meta:
        verbose_name = 'profile'
        verbose_name_plural = 'profiles'
        app_label = 'core'
