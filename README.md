<img src="app/escriptorium/static/images/transcriptus-icon.svg" alt="" width="96" align="right">

# Transcriptus

Transcriptus is a platform to transcribe, annotate and publish historical documents, built on [eScriptorium](https://gitlab.com/scripta/escriptorium). It keeps eScriptorium's pipeline (automatic transcription with kraken, search, annotation, sharing and versioning) and adds its own interface changes and the TEI (Ephrem) export ([docs/tei](docs/tei/)).

Its logo is *Julidochromis transcriptus*, the fish the name comes from.

## The stack
- nginx
- uwsgi
- [django](https://www.djangoproject.com/)
- [daphne](https://github.com/django/daphne) (channel server for websockets)
- [celery](http://www.celeryproject.org/)
- postgres
- [elasticsearch](https://www.elastic.co/)
- redis (cache, celery broker, other disposable data)
- [kraken](http://kraken.re)
- [docker](https://www.docker.com/) (deployment)


## Install
Two options,
- [install with Docker](https://gitlab.com/scripta/escriptorium/-/wikis/docker-install), or a
- [full local install](https://gitlab.com/scripta/escriptorium/-/wikis/full-install).

Transcriptus needs either Linux, macOS or Windows (with WSL). The install guides are eScriptorium's: follow them with this repository in place of eScriptorium's.


## Development scripts

Two helper scripts cover the day-to-day docker workflow. They need Node 18+ and
can be run through npm from the repository root or directly with node.

| Task | npm | node |
| --- | --- | --- |
| Full rebuild: stop, rebuild images, start, wait for healthy | `npm run rebuild` | `node scripts/rebuild.mjs` |
| Same, but rebuild every layer from scratch | `npm run rebuild:clean` | `node scripts/rebuild.mjs --no-cache` |
| Refresh only the UI: build `front/` and copy it into the running containers | `npm run ui` | `node scripts/refresh-ui.mjs` |
| Same, but keep rebuilding and syncing on every file save | `npm run ui:watch` | `node scripts/refresh-ui.mjs --watch` |

The UI refresh takes a few seconds and does not restart anything: the webpack
bundles are built on the host and copied into the `static` volume that nginx
serves, so a browser refresh shows the change. Restarting the `web` container
restores the bundles baked into the image, so run the refresh again (or a full
rebuild) after that. Backend, template or dependency changes need `npm run rebuild`.

On Linux the scripts fall back to `sudo docker` automatically when the daemon
is not reachable as the current user; pass `--sudo` to force it. Every script
accepts `--help`.

## Contributing
Changes go through pull requests on this repository. For the upstream project, see [Contributing to eScriptorium](https://gitlab.com/scripta/escriptorium/-/wikis/contributing).

## License

Transcriptus is released under the [MIT license](LICENSE). It is a derivative of [eScriptorium](https://gitlab.com/scripta/escriptorium), which is also MIT-licensed and used here under those terms. The license file keeps both copyright notices: Transcriptus (© 2026 Colorado Christian University) and eScriptorium (© 2018 Robin Tissot, PSL). The MIT terms require that these notices and the permission text are included in all copies or substantial portions of the software.

## Built on eScriptorium

Transcriptus is a fork of eScriptorium, and the credits below are eScriptorium's own. The upstream project is at <https://gitlab.com/scripta/escriptorium>.

eScriptorium is part of the [Scripta](https://www.psl.eu/en/scripta), [RESILIENCE](https://www.resilience-ri.eu) and [Biblissima+](https://projet.biblissima.fr/) projects, and has received funding from Université PSL and from The European Union's [Horizon 2020 Research and Innovation Programme](https://ec.europa.eu/programmes/horizon2020/en/what-horizon-2020) under Grant Agreement no. 871127, from the Programme d'investissements d'avenir of the [Agence Nationale de Recheche](https://anr.fr/fr/france-2030/france-2030/) under Grant Reference no. ANR-21-ESRE-0005, as well as from other contributors listed below. Its goal is provide researchers in the humanities with an integrated set of tools to transcribe, annotate, translate and publish historical documents.
The eScriptorium app itself is at the 'center'. It is a work in progress but will implement at least automatic transcriptions through kraken, indexation for complex search and filtering, annotation and some simple forms of collaborative working such as sharing and versioning.

### eScriptorium steering committee

- Daniel Stoekl Ben Ezra (EPHE-PSL, UMR AOROC 8546)
- Peter Stokes (EPHE-PSL, UMR AOROC 8546)
- Benjamin Kiessling (EPHE-PSL, UMR AOROC 8546)
- Robin Tissot (EPHE-PSL, UMR AOROC 8546)
- Mathew Barber (Aga Khan University, Institute for the Study of Muslim Civilisations)
- David Smith (Northeastern University)
- Thibault Clérice (Inria)
- Hassen Aguili (Inria)

### eScriptorium's current financial and technical contributors include:
- [École Pratique des Hautes Études (EPHE)](https://www.ephe.psl.eu)
- [Biblissima+](https://projet.biblissima.fr/)
- [Resilience](https://www.resilience-ri.eu/)
- [PSL Scripta](https://scripta.psl.eu/en/)
- [Institut national de recherche en sciences et technologies du numérique (INRIA)](https://inria.fr/en)
- [Archives nationales de France](https://www.archives-nationales.culture.gouv.fr/)
- [L’Institut de recherche et d’histoire des textes](https://www.irht.cnrs.fr/)
- [Open Islamicate Texts Initiative (OpenITI)](https://openiti.org/)
- [The Andrew W. Mellon Foundation](https://mellon.org/grants/)
