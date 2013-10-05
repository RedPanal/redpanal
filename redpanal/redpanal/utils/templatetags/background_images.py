import random
from django import template

register = template.Library()

class BackgroundImage(object):

    def __init__(self, name, filename, author, link, license):
        self.name = name
        self.filename = filename
        self.author = author
        self.link = link
        self.license = license

BI = BackgroundImage

BACKGROUND_IMAGES = (
  BI(u"Music guitar", "4542297929_c25ee7495e_o.jpg", u"doug88888",
     "http://www.flickr.com/photos/doug88888/4542297929/", "by-nc-sa"),
  BI(u"Music", "357532726_3f96bf2578_o.jpg", u"Sameer Vasta",
     "http://www.flickr.com/photos/vasta/357532726/", "by-nc-nd"),
  BI(u"Future Music Festival 2013", "8540647429_76995ae051_o.jpg", u"Eva Rinaldi",
     "http://www.flickr.com/photos/evarinaldiphotography/8540647429/", "by-sa"),
  BI(u"The Music Moves Me", "3339038251_be7e12ed99_o.jpg", u"mbtphoto",
     "http://www.flickr.com/photos/marybaileythomas/3339038251/", "by-nd"),
)



@register.assignment_tag
def get_background_image():
    return random.choice(BACKGROUND_IMAGES)
