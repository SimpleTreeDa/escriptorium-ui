import json

from django.core.management.base import BaseCommand, CommandError

from core.models import Document, Project
from imports.serializers import OntologyImportSerializer
from imports.tei.profile import ONTOLOGY


class Command(BaseCommand):
    help = (
        "Add the Ephrem ontology (the region types, line types and annotation taxonomies "
        "of the Ephrem TEI profile) to documents. Running it again changes nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument("documents", nargs="*", type=int, help="Document ids")
        parser.add_argument("--project", help="Every document of this project (id or slug)")
        parser.add_argument("--file", help="An ontology JSON file to apply instead of the Ephrem ontology")

    def handle(self, *args, **options):
        documents = list(Document.objects.filter(pk__in=options["documents"]).order_by("pk"))
        missing = set(options["documents"]) - {document.pk for document in documents}
        if missing:
            raise CommandError("No document with id %s" % ", ".join(str(pk) for pk in sorted(missing)))
        if options["project"]:
            lookup = {"pk": options["project"]} if options["project"].isdigit() else {"slug": options["project"]}
            try:
                project = Project.objects.get(**lookup)
            except Project.DoesNotExist:
                raise CommandError(f"No project {options['project']}")
            documents += [document for document in project.documents.order_by("pk") if document not in documents]
        if not documents:
            raise CommandError("Give document ids or --project")

        ontology = ONTOLOGY
        if options["file"]:
            with open(options["file"], encoding="utf-8") as fh:
                ontology = json.load(fh)
        if ontology.get("version") != OntologyImportSerializer.VERSION:
            raise CommandError(f"The ontology is in version {ontology.get('version')}, "
                               f"only version {OntologyImportSerializer.VERSION} is supported")

        for document in documents:
            report = []  # the serializer appends its messages, as to a TaskReport
            serializer = OntologyImportSerializer(document, data=ontology, report=report)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            self.stdout.write("Document %s (%s):" % (document.pk, document.name))
            for line in report:
                self.stdout.write("  " + line)
