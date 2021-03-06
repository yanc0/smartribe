from django.conf import settings
from django.utils.translation import ugettext as _
from django.db import models

from core.models.offer import Offer
from core.models.meeting_point import MeetingPoint




class Meeting(models.Model):

    offer = models.ForeignKey(Offer)

    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    meeting_point = models.ForeignKey(MeetingPoint)

    date_time = models.DateTimeField()

    STATUS_CHOICES = (
        ('P', _('Pending')),
        ('A', _('Accepted')),
        ('R', _('Refused')),
    )
    status = models.CharField(max_length=1,
                              choices=STATUS_CHOICES,
                              default='P')

    is_validated = models.BooleanField(default=False)

    creation_date = models.DateTimeField(auto_now_add=True)

    last_update = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.id) + ' - Date : ' + str(self.date_time) + ' - Offer : ' + str(self.offer)

    class Meta:
        verbose_name = _('meeting')
        verbose_name_plural = _('meetings')
        app_label = 'core'
