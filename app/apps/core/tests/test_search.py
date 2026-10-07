from django.test import SimpleTestCase

from core.search import (
    WORD_BY_WORD_SEARCH_MODE,
    build_highlighted_replacement_psql,
    escape_highlighted,
)


class EscapeHighlightedTestCase(SimpleTestCase):
    """The text of search results is shown as text, only the highlighting is markup"""

    def test_text_is_escaped(self):
        """Markup in the line text is escaped, the highlight tags are kept"""
        highlighted = '<img src=x onerror=alert(1)> Rex & <strong class="text-success">regina</strong>'
        self.assertEqual(
            escape_highlighted(highlighted),
            '&lt;img src=x onerror=alert(1)&gt; Rex &amp; <strong class="text-success">regina</strong>',
        )

    def test_replacement_term_is_escaped(self):
        """The replacement term typed in the search form is escaped too"""
        highlighted = 'Rex <strong class="text-danger">regina</strong>'
        preview = build_highlighted_replacement_psql(
            WORD_BY_WORD_SEARCH_MODE, "regina", "<img src=x onerror=alert(1)>", highlighted)
        self.assertEqual(
            escape_highlighted(preview),
            'Rex <strong class="text-success">&lt;img src=x onerror=alert(1)&gt;</strong>',
        )

    def test_other_tags_are_escaped(self):
        """Only the exact highlight tags are kept"""
        self.assertEqual(
            escape_highlighted('<strong class="x" onclick="alert(1)">a</strong>'),
            '&lt;strong class=&quot;x&quot; onclick=&quot;alert(1)&quot;&gt;a</strong>',
        )

    def test_empty(self):
        self.assertIsNone(escape_highlighted(None))
        self.assertEqual(escape_highlighted(""), "")
