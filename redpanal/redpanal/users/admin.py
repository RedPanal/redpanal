from django.contrib import admin
from models import DefaultFollowedUser

class DefaultFollowedUserAdmin(admin.ModelAdmin):
    list_display = ('user', )
    
admin.site.register(DefaultFollowedUser, DefaultFollowedUserAdmin)
