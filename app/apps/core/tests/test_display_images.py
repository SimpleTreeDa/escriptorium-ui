from io import BytesIO, StringIO

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from easy_thumbnails.files import get_thumbnailer
from PIL import Image

from core.tasks import generate_part_thumbnails
from core.tests.factory import CoreFactoryTestCase


class DisplayImageTestCase(CoreFactoryTestCase):
    """TIFF pages get a full size 'display' thumbnail since browsers can't render TIFF."""

    def make_image_part(self, name, fmt, **kwargs):
        # wider than the 'large' alias so we can tell a full size copy from a downscaled one
        buf = BytesIO()
        Image.new('RGB', size=(1200, 100), color=(155, 0, 0)).save(buf, fmt)
        image = SimpleUploadedFile(name=name, content=buf.getvalue())
        return self.factory.make_part(image=image, image_file_size=len(buf.getvalue()), **kwargs)

    def get_display(self, part):
        return get_thumbnailer(part.image).get_thumbnail(
            settings.THUMBNAIL_ALIASES['']['display'], generate=False)

    def test_needs_display_image(self):
        self.assertTrue(self.make_image_part('page.tif', 'TIFF').needs_display_image)
        self.assertTrue(self.make_image_part('PAGE.TIFF', 'TIFF').needs_display_image)
        self.assertFalse(self.make_image_part('page.png', 'PNG').needs_display_image)
        self.assertFalse(self.make_image_part('page.jpg', 'JPEG').needs_display_image)

    def test_thumbnails_task_generates_full_size_display_for_tiff(self):
        part = self.make_image_part('page.tif', 'TIFF')
        aliases = generate_part_thumbnails(instance_pk=part.pk)
        self.assertIn('display', aliases)
        display = self.get_display(part)
        self.assertEqual((display.width, display.height), (1200, 100))
        self.assertTrue(display.name.endswith('.jpg'))

    def test_thumbnails_task_skips_display_for_browser_formats(self):
        part = self.make_image_part('page.png', 'PNG')
        aliases = generate_part_thumbnails(instance_pk=part.pk)
        self.assertNotIn('display', aliases)
        self.assertIn('large', aliases)
        self.assertIsNone(self.get_display(part))

    def test_part_detail_exposes_display(self):
        tiff = self.make_image_part('page.tif', 'TIFF')
        png = self.make_image_part('page.png', 'PNG', document=tiff.document)
        generate_part_thumbnails(instance_pk=tiff.pk)
        generate_part_thumbnails(instance_pk=png.pk)
        self.client.force_login(tiff.document.owner)

        for part, has_display in ((tiff, True), (png, False)):
            uri = reverse('api:part-detail', kwargs={'document_pk': part.document.pk, 'pk': part.pk})
            resp = self.client.get(uri)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual('display' in resp.json()['image']['thumbnails'], has_display)

    def test_generate_display_images_command(self):
        tiff = self.make_image_part('page.tif', 'TIFF')
        other_doc_tiff = self.make_image_part('other.tiff', 'TIFF')
        png = self.make_image_part('page.png', 'PNG', document=tiff.document)

        out = StringIO()
        call_command('generate_display_images', document=tiff.document.pk, stdout=out)
        self.assertIsNotNone(self.get_display(tiff))
        self.assertIsNone(self.get_display(other_doc_tiff))
        self.assertIsNone(self.get_display(png))
        self.assertIn('1 generated, 0 failed', out.getvalue())

        call_command('generate_display_images', stdout=StringIO())
        self.assertIsNotNone(self.get_display(other_doc_tiff))
