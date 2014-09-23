from django.db import models
from django.contrib.auth.models import User


class SkillCategory(models.Model):

    name = models.CharField(max_length=50)

    detail = models.TextField()

    def __str__(self):
        return self.name

    class Meta():
        verbose_name = 'skill category'
        verbose_name_plural = 'skill categories'
        app_label = 'core'


class Skill(models.Model):
    user = models.ForeignKey(User)

    category = models.ForeignKey(SkillCategory)

    description = models.TextField()

    MEDIUM = 1
    HIGH = 2
    EXPERT = 3
    LEVEL_CHOICES = (
        (MEDIUM, 'Medium'),
        (HIGH, 'High'),
        (EXPERT, 'Expert')
    )
    level = models.IntegerField(default=MEDIUM,
                                choices=LEVEL_CHOICES)

    def __str__(self):
        return self.description

    class Meta:
        verbose_name = 'skill'
        verbose_name_plural = 'skills'
        app_label = 'core'
