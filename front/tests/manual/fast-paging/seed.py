# Seed for the fast-paging check (see README.md). Run inside the web container:
#   docker exec -i <web container> python manage.py shell < front/tests/manual/fast-paging/seed.py
# Idempotent: creates (or completes) one document with N generated pages.
# Page n shows "PAGE n" and 5 + (n % 7) grey rules, and has the same number of
# segmentation lines, so the overlay can be checked against the image shown.
import io
import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

from core.models import Block, Document, DocumentPart, Line, Project

User = get_user_model()
DOC_NAME = "Fast paging test (issue #6)"
N = 200
W, H = 600, 800

# created by the users migration 0004 from DJANGO_SU_* in variables.env
user = User.objects.get(username=os.environ.get("DJANGO_SU_NAME", "admin"))
if user.legacy_mode:
    user.legacy_mode = False  # the new UI
    user.save(update_fields=["legacy_mode"])

project = Project.objects.filter(name="Issue 6 reproduction").first() or Project.objects.create(
    name="Issue 6 reproduction", owner=user)
doc = Document.objects.filter(name=DOC_NAME, project=project).first() or Document.objects.create(
    name=DOC_NAME, owner=user, project=project)

try:
    font = ImageFont.load_default(size=64)
except TypeError:  # older Pillow
    font = ImageFont.load_default()


def rules(i):
    return 5 + (i % 7)


existing = doc.parts.count()
for i in range(existing, N):
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([30, 30, W - 30, H - 30], outline="black", width=4)
    d.text((60, 50), f"PAGE {i + 1}", fill="black", font=font)
    ys = [160 + k * 60 for k in range(rules(i))]
    for y in ys:
        d.line([(80, y), (W - 80, y)], fill=(120, 120, 120), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    data = buf.getvalue()

    part = DocumentPart(document=doc, name=f"page {i + 1:03d}",
                        original_filename=f"page{i + 1:03d}.png",
                        image_file_size=len(data),
                        workflow_state=DocumentPart.WORKFLOW_STATE_SEGMENTED)
    part.image.save(f"page{i + 1:03d}.png", ContentFile(data), save=False)
    part.save()

    block = Block.objects.create(
        document_part=part,
        box=[[60, 120], [W - 60, 120], [W - 60, ys[-1] + 40], [60, ys[-1] + 40]])
    for y in ys:
        Line.objects.create(document_part=part, block=block,
                            baseline=[[80, y], [W - 80, y]],
                            mask=[[80, y - 22], [W - 80, y - 22], [W - 80, y + 10], [80, y + 10]])
    if (i + 1) % 50 == 0:
        print("created", i + 1, "pages")

first = doc.parts.order_by("order").first()
print("DOC_PK", doc.pk, "PARTS", doc.parts.count(), "FIRST_PART_PK", first.pk,
      "EDITOR_URL", f"/document/{doc.pk}/part/{first.pk}/edit/")
