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
        BI(u"RedPanal", "simulaciones.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "apicultor.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "pablo.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "guitarra.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back1.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back2.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back3.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back4.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back5.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back6.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back7.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back8.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back10.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back11.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back14.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back15.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back16.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
        BI(u"RedPanal", "back17.jpg", u"RedPanal",
     "http://redpanal.org", "by-sa"),
)



@register.simple_tag
def get_background_image():
    return random.choice(BACKGROUND_IMAGES)

