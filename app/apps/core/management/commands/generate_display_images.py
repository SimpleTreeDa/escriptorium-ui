import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from easy_thumbnails.files import get_thumbnailer

from core.models import DocumentPart

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generate the full size 'display' image of existing TIFF pages, which browsers can't render, "
        "so the editor shows them at full resolution instead of the 1000px 'large' thumbnail. "
        "New uploads get it automatically."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--document",
            type=int,
            help="Only process the pages of the document with this pk.",
        )

    def handle(self, *args, **options):
        parts = DocumentPart.objects.filter(
            Q(image__iendswith=".tif") | Q(image__iendswith=".tiff")
        ).order_by("document", "order")
        if options["document"]:
            parts = parts.filter(document=options["document"])

        total = parts.count()
        failed = 0
        config = settings.THUMBNAIL_ALIASES[""]["display"]
        for i, part in enumerate(parts.iterator(), start=1):
            try:
                get_thumbnailer(part.image).get_thumbnail(config)
            except Exception:
                failed += 1
                logger.exception("Could not generate the display image of part %d", part.pk)
            else:
                self.stdout.write(f"[{i}/{total}] {part.image.name}")

        self.stdout.write(self.style.SUCCESS(f"Done: {total - failed} generated, {failed} failed."))
