from django.template import Library, loader, Context
from django.conf import settings
import urllib.parse

register = Library()


@register.simple_tag(takes_context=True)
def game_template(context, template_name):
    t = loader.get_template(f'{template_name}.html')
    
    return t.render(context.flatten())


@register.simple_tag(takes_context=True)
def game_static(context, static_name, static_type):
    return urllib.parse.urljoin(settings.STATIC_URL, f'{static_name}.{static_type}')
