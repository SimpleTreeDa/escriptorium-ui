from django import template

from core.search import escape_highlighted

register = template.Library()
register.filter("escape_highlighted", escape_highlighted)
