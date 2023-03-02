from django.contrib import admin
from .models import DefaultFollowedUser
from audio.models import Audio #BORRAME

class DefaultFollowedUserAdmin(admin.ModelAdmin):
    list_display = ('user', )
    
admin.site.register(DefaultFollowedUser, DefaultFollowedUserAdmin)
admin.site.register(Audio) #BORRAME