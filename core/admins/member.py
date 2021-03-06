from core.admins.basic import BasicAdmin
from core.models import Member


class MemberAdmin(BasicAdmin):
    model = Member
    list_display = ['user', 'community', 'role', 'status', 'id']
    list_editable = ['role', 'status']
    search_fields = ['user__username', 'community__name']
    list_filter = ['role', 'status']