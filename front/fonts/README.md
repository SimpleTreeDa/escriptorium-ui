# Fonts

Declared with `@font-face` in `front/vue/index.css`.

## Noto Sans

`NotoSans-*.ttf`: the interface and the text of Latin scripts.

## Noto Sans Syriac

So that Syriac text does not depend on the fonts installed on the user's
computer. The user picks one of the three variants for each document, in the
editor's **Text** menu (`front/src/editor/syriacFont.js`):

| Variant | Family | Files |
|---|---|---|
| Estrangela (default) | Noto Sans Syriac | `NotoSansSyriac-Regular.woff2`, `NotoSansSyriac-Bold.woff2` |
| Serto (West Syriac) | Noto Sans Syriac Western | `NotoSansSyriacWestern-Regular.woff2`, `NotoSansSyriacWestern-Bold.woff2` |
| East Syriac | Noto Sans Syriac Eastern | `NotoSansSyriacEastern-Regular.woff2`, `NotoSansSyriacEastern-Bold.woff2` |

- **License:** SIL Open Font License 1.1, in `OFL-NotoSansSyriac.txt`
  (the same for the three variants).
- **Source:** the "syriac" subsets (weights 400 and 700) of the Fontsource
  packages `@fontsource/noto-sans-syriac`, `@fontsource/noto-sans-syriac-eastern`
  and `@fontsource/noto-sans-syriac-western` 5.3.0, built from the Google Fonts
  files (github.com/google/fonts, version v18).
- **Characters:** the Syriac block (U+0700–074F, except U+070E, U+074B and
  U+074C, which are unassigned) and what Syriac text uses with it: combining
  marks, among them seyame (U+0308), Arabic vowel signs for Garshuni, the
  tatweel, the joiners U+200C–200F, the dotted circle U+25CC, and the crosses
  U+2670–2671. The `unicode-range` of the `@font-face` rules lists them, so
  that the fonts are only used, and downloaded, for these characters. The
  Syriac Supplement block (U+0860–086F) is in the range but not in these fonts:
  its characters come from the other fonts of the list.

To update: download the packages with `npm pack`, copy
`files/noto-sans-syriac*-syriac-{400,700}-normal.woff2` under the names above,
and compare the characters of the new files with the `unicode-range`.
