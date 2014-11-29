from django.contrib import admin
from models import DefaultFollowedUser

class DefaultFollowedUserAdmin(admin.ModelAdmin):
    pass
    
admin.site.register(DefaultFollowedUser, DefaultFollowedUserAdmin)
