from django.contrib import admin
from .models import DefaultFollowedUser
from audio.models import Audio

@admin.register(DefaultFollowedUser)
class DefaultFollowedUserAdmin(admin.ModelAdmin):
    list_display = ('user', )
    
admin.site.register(Audio)
