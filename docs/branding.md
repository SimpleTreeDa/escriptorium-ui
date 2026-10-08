# Branding

The platform is called **Transcriptus**. It is built on [eScriptorium](https://gitlab.com/scripta/escriptorium), and the home page, credits page, README and `LICENSE` say so.

## The logo

The logo is *Julidochromis transcriptus*, the fish the name comes from.

The source artwork is a traced image: white markings on a dark fish against a black background. The trace drew a black square and cut the markings out of it as holes. In the files below that square is removed, so the markings are the shape, and the view is cropped to the fish.

| File | What it is | Used by |
|---|---|---|
| `front/vue/components/Icons/TranscriptusLogo/TranscriptusLogo.vue` | The markings, in the theme's text colour (`--text1`), 56px wide | The global navigation |
| `app/escriptorium/static/images/transcriptus-logo.svg` | The markings in white, for dark backgrounds | The legacy-mode navbar |
| `app/escriptorium/static/images/transcriptus-icon.svg` | The white markings on a dark rounded tile (`#212323`) | The SVG favicon and the README |
| `app/escriptorium/static/images/favicon.ico` | The tile at 16, 32 and 48 px | Browsers, and nginx's `/favicon.ico` |
| `app/escriptorium/static/images/apple-touch-icon.png` | The tile at 180 px | iOS home screens |

The PNG and ICO files are renders of `transcriptus-icon.svg`. If the artwork changes, make them again from that SVG.

## Names that still say eScriptorium, on purpose

These are internal names or stored data. Renaming them changes nothing that people see, and some renames would lose data:

- **The database name** `POSTGRES_DB=escriptorium`. A new name points the app at a new, empty database.
- **The Docker volumes and the compose project**, both named after the checkout folder. Renaming the project, or adding `name:` to `docker-compose.yml`, creates new empty volumes.
- **`VERSIONING_DEFAULT_SOURCE = 'eScriptorium'`.** It is stored on every line version, and it marks lines that people typed in the editor rather than model output. The version-compare view and the TEI credits both depend on it.
- **The `escriptorium` Python package** and `DJANGO_SETTINGS_MODULE`, the celery app, the nginx upstream, `ESCRIPTORIUM_ENV`, the `escr-` CSS prefix and `<body id="escriptorium">`. These match upstream, which keeps merges from eScriptorium simple.
- **The localStorage key `escriptorium.userProfile`.** Renaming it resets everyone's saved preferences.
- **`@escriptorium/virtual-keyboard`**, a third-party package, and the upstream base image `registry.gitlab.com/scripta/escriptorium/base`.
- **Upstream links and credits**: the eScriptorium community links on the home page, the funders' logos, `contributors_example/`, and the eScriptorium copyright notice in `LICENSE`, which the MIT licence requires.

## Site name

Django's password-reset email names the site from the `Site` row. Migration `users/0024` sets that row from `SITE_NAME` and `DOMAIN`. It covers two cases:

- **A new database.** Django adds an `example.com` row only after all migrations have run, so migration 0015 never had a row to fill. Migration 0024 creates the row first.
- **An existing site** still called "example.com" or "escriptorium". It gets `SITE_NAME`, or Transcriptus if `SITE_NAME` is unset or still the old default, and `DOMAIN` if its domain is still "example.com".

A site name someone chose is left alone.
