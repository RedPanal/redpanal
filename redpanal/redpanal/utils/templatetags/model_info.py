from django import template

register = template.Library()

def get_verbose_name(object): 
    return object._meta.verbose_name

register.filter('get_verbose_name', get_verbose_name)
