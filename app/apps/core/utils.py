import random
import unicodedata

from django.db.models import CharField
from django.forms.widgets import Input


def random_color():
    return "#%06x" % random.randint(0, 0xFFFFFF)


class ColorWidget(Input):
    input_type = 'color'
    template_name = 'core/widgets/color.html'


class ColorField(CharField):
    def __init__(self, *args, **kwargs):
        kwargs['max_length'] = 7
        kwargs['default'] = random_color
        super(ColorField, self).__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs['widget'] = ColorWidget
        return super(ColorField, self).formfield(**kwargs)


# the Unicode normalization form of the text of line transcriptions
TEXT_NORMALIZATION_FORM = 'NFC'


def normalize_text(text):
    """
    Return the text in Unicode NFC, the form line transcriptions are stored in,
    so that text that looks the same is the same sequence of code points: for
    search, statistics, training and exports.

    NFC composes a letter and its combining marks when Unicode has a
    precomposed character for them (e + U+0301 becomes é), and puts combining
    marks in their canonical order. Syriac vowel points have no precomposed
    forms: text already in canonical order is unchanged.

    None and the empty string are returned as they are.
    """
    if not text or unicodedata.is_normalized(TEXT_NORMALIZATION_FORM, text):
        return text
    return unicodedata.normalize(TEXT_NORMALIZATION_FORM, text)
