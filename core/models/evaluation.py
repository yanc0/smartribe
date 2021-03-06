from django.utils.translation import ugettext as _
from django.db import models
from core.models.meeting import Meeting
from core.models.offer import Offer
from core.models.reportable_model import ReportableModel


class Evaluation(ReportableModel):

    offer = models.ForeignKey(Offer)

    DANGEROUS = 0
    BAD = 1
    NEUTRAL = 2
    GOOD = 3
    EXCELLENT = 4
    PERFECT = 5
    EVALUATION_CHOICES = (
        (DANGEROUS, 'Dangerous'),
        (BAD, 'Bad'),
        (NEUTRAL, 'Neutral'),
        (GOOD, 'Good'),
        (EXCELLENT, 'Excellent'),
        (PERFECT, 'Perfect'),
    )
    mark = models.IntegerField(choices=EVALUATION_CHOICES)

    usefull = models.BooleanField(default=True)

    comment = models.TextField()

    creation_date = models.DateTimeField(auto_now_add=True)

    last_update = models.DateTimeField(auto_now=True)

    def had_meeting(self):
        if Meeting.objects.filter(offer=self.offer).exists():
            return True
        return False

    def __str__(self):
        return self.offer.user.email + ', ' + self.id.__str__()

    class Meta:
        verbose_name = _('evaluation')
        verbose_name_plural = _('evaluations')
        app_label = 'core'