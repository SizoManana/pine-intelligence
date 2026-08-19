# DESIGN.md

The design language of this site, written so another person or an AI agent can extend it without
guessing. Everything below is implemented in `assets/css/site.css`.

---

## Intent

Bold, block based, high contrast. Structure and styling are adapted from a print styled editorial
resume reference: a dark fixed sidebar, filled colour bars as section headings, heavy uppercase
display type, solid colour blocking, and a full bleed black and white portrait.

Two rules override any aesthetic preference:

1. **The page must not undermine its own claims.** A site arguing for measurement, accessibility and
   performance cannot ship layout shift, invisible focus rings or a slow hero.
2. **No em dashes in the copy.** Commas, colons and full stops. No en dashes either.

Third rule, added after a specific mistake: **no number appears on this site unless it was measured
and can be traced.** No rounded estimates, no illustrative figures, no borrowed industry statistics.
Where a project has no measured outcome, it says so rather than filling the space.

---

## Colour

Near black with a green cast, warm off white paper, one emerald accent. Light and dark are both
designed, not inverted.

| Token | Light | Dark | Use |
|---|---|---|---|
| `--ink` | `#0b1410` | `#f1f3f0` | Body text, headings |
| `--ink-2` | `#3f4a44` | `#bfc6c1` | Secondary text, lede |
| `--ink-3` | `#5d6862` | `#959e98` | Captions, metadata, labels |
| `--paper` | `#f8f7f3` | `#0b100d` | Page background |
| `--paper-2` | `#efeee8` | `#121a16` | Alternating band |
| `--paper-3` | `#e4e3db` | `#1a231e` | Image placeholder, code |
| `--line` | `#d6d5cc` | `#26302a` | All borders |
| `--green` | `#0b6e4f` | `#2fc98a` | Bars, buttons, accents, links |
| `--green-deep` | `#08553d` | `#25a570` | Button hover |
| `--on-green` | `#ffffff` | `#04150e` | Text on emerald fill |
| `--green-on-dark` | `#35d497` | `#35d497` | Accents and links on dark surfaces, both schemes |
| `--dark` | `#0c1712` | `#121a16` | Sidebar, footer, `.ink` sections |
| `--on-dark` / `--on-dark-2` | `#f2f5f2` / `#a9b6ae` | same | Text on dark |

One trap found the hard way: `section.ink a` sets links to the bright accent, and a filled `.btn` is
an anchor, so inside a dark section the button rendered accent text on an accent fill. Buttons carry
an explicit `section.ink a.btn` override. Any new element that is both an anchor and a filled surface
needs the same treatment.

**Every pair clears WCAG AA for body text at 4.5:1.** Measured, not assumed. The lowest is
`--ink-3` on `--paper-2` at 4.99:1. A validator in the build computes all 21 pairs and reports any
that drop below the threshold.

### The one place the reference could not be copied

The reference uses **black type on yellow**. Yellow is a light hue, so black on yellow measures about
11:1. Emerald is a **dark** hue: near black on emerald measures 2.99:1 and fails outright, while
white on emerald measures 6.25:1.

So type on emerald is white here, not black. That is the same contrast logic as the reference,
inverted by the hue. It is not a softening of the reference, it is the reference applied correctly to
a different colour.

`--green-on-dark` exists for a second reason found the same way: the light mode emerald sitting on a
dark sidebar or footer measures 2.93:1. Accents on dark surfaces use the brighter green in both
schemes.

---

## Type

**No web fonts.** Stated openly on the site. Nothing to download, no invisible text during a font
swap, no third party request.

- Everything: system sans stack (`ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, …`)
- Code, counters and browser chrome labels: system mono stack

The reference's impact comes mostly from weight, scale, tracking and colour blocking rather than from
its typeface, so the system stack carries it. Trade off worth knowing: a geometric display face would
get closer to the reference, at the cost of the no third party request promise. The promise was kept.

- `h1`: `--step-4`, weight 800, uppercase, `letter-spacing: -.028em`, `line-height: 1.05`
- `h2`, `h3`: weight 800, sentence case, tight tracking
- Bar headings, eyebrows, kickers, buttons, nav: uppercase, weight 800, `letter-spacing` .1em to .2em
- Body: `line-height: 1.62`, `text-wrap: pretty`. Headings `text-wrap: balance`
- Numbers in metric blocks: `font-variant-numeric: tabular-nums`
- Measure: `--readw` is `72ch` for prose, `90ch` where prose carries figures

### Copy conventions

- **Sentence case for editorial headings and h1 in uppercase via CSS.** Title Case for buttons and
  navigation only.
- First person. This is a portfolio, not product UI.
- Curly quotes. The ellipsis character, never three full stops.
- `translate="no"` on role labels so machine translation does not garble them.

Note on the Vercel Web Interface Guidelines, which this site was built against: it calls for Title
Case on all headings and second person prose. Both are right for product interface copy and wrong for
editorial writing, so they were adopted for buttons and navigation and declined for headings and
body. That is a decision, not an oversight.

---

## Layout

- `--side` is `236px`. Below 1080px the sidebar becomes a sticky top bar and `body` loses its left
  padding. Above 1080px the sidebar is `position: fixed` full height, with the contact rail pinned to
  the bottom.
- `.wrap` is the `1120px` container. `.narrow` is the prose column, `.narrow.wide` for prose with
  figures.
- Sections alternate `--paper`, `.alt` (`--paper-2`) and `.ink` (dark). Never three of the same in a
  row.
- **No border radius anywhere.** Squared corners are part of the reference language.
- Borders are `1.5px` on content, `2px` or `3px` where a rule is doing structural work. Depth comes
  from borders, background steps and solid blocks, never from shadow. There are no shadows.

---

## Components

| Component | Purpose | Rules |
|---|---|---|
| `.sidebar` | Fixed nav | Dark. Uppercase nav, emerald glyph mark, emerald underline on the current page, emerald CTA. Collapses to a sticky top bar under 1080px |
| `.barhead` | Section heading | Solid emerald bar, white uppercase text, wide tracking. The signature device |
| `.hero-split` | Page opener | Heavy uppercase h1 with `<mark>` for the emerald highlight block, beside a full bleed black and white portrait with an emerald stamp |
| `.card` | Project card | Bordered, 16:10 cover in a `.shot` wrapper, emerald number badge top left, uppercase kicker, hover lifts and turns the border emerald |
| `.ba` | Before and after | Two figures side by side, stacked under 820px. Before tag is ink, after tag is emerald. Never a drag slider |
| `.scroller` | Full page viewer | Dark browser bar with a mono label, `max-height: min(70vh, 620px)`, `overscroll-behavior: contain`, pane focusable with `tabindex="0"` and an `aria-label` |
| `.metrics` | Measured figures | Bordered grid, emerald tabular number. **Only used where the number was measured.** Pages without measured outcomes have no metric block |
| `.pillars` | Structure diagram | Hairline grid of numbered blocks. Always captioned as a diagram, never presented as a screenshot |
| `.flow` | Sequence diagram | Numbered rows with a mono counter, emerald top rule |
| `.callout` | Aside | Left emerald border on a wash. `.win` for what I would do differently, `.note` for a caveat. Title is a `<p class="callout-title">`, never a heading, so the outline stays clean |
| `.pull` | Pull quote | Heavy, emerald top rule, one per page maximum |
| `.video` | Lazy video | A real `<button>` with `aria-label`. Nothing loads from YouTube until pressed, then a `youtube-nocookie.com` iframe replaces the button |
| `.timeline` | Career arc | An `<ol>` with a rail, nodes that activate as they pass 58 percent of the viewport, and a fill height driven by a `--fill` custom property. The fill is a pseudo element, not a child span, because a span is not valid inside an `<ol>` |
| `.jumpnav` | Long form navigation | Sticky section links with an active state tracked by `IntersectionObserver`. Used on pages long enough that a reader needs to know where they are |
| `.progress` | Reading progress | A fixed 3px bar driven by `transform: scaleX()`, offset by the sidebar width on desktop. Hidden entirely under reduced motion |
| `.reveal` | Long image disclosure | Full page mobile designs run to 10,000 pixels and more. Clipped to 600px with a fade, expanded by a real `<button>` carrying `aria-expanded`. The clip is applied by script on load, so with JavaScript off the full image simply shows rather than being hidden |

### Before and after: why not a slider

A drag slider is a gesture only interaction, needs keyboard and tap alternatives, performs badly on
long images, and makes the visitor work to see the comparison. The comparison is the content, so it
should not sit behind an interaction.

### Diagrams are labelled as diagrams

`.pillars` and `.flow` render structures documented in a brief, drawn for the site. Every instance
carries a caption saying so. A diagram presented as a product screenshot is a fabrication, and this
site had one fabricated section in an early draft, which is why the rule is written down.

---

## Motion

- Only `transform`, `opacity`, `background-color`, `border-color`, `color`. Never `transition: all`.
- Disclosure is instant, not animated. Expanding a 10,000 pixel image with a height transition is a
  jank generator for no benefit.
- 160ms, `ease`.
- Every transition and the smooth scroll are disabled under `prefers-reduced-motion: reduce`.
- No scroll driven animation, no entrance animation, no parallax.

---

## Accessibility, non-negotiable

- Skip link first in the DOM.
- `:focus-visible`, `3px` emerald outline, `3px` offset. `outline: none` appears nowhere.
- Semantic HTML first. Buttons for actions, anchors for navigation. No `<div>` with a click handler.
- Headings strictly hierarchical, one `h1` per page, no level skipped. Validated.
- Real alt text on every image, describing what it shows. Never "screenshot".
- `[id] { scroll-margin-top: 5rem }` so anchors clear the sticky bar.
- `env(safe-area-inset-*)` on the sidebar and footer.
- `touch-action: manipulation`. Zoom never disabled.

---

## Performance budget

| Item | Budget | Actual |
|---|---|---|
| CSS | under 25 KB | about 21 KB, one file, no framework |
| JavaScript | under 4 KB | about 2.8 KB, for the reading progress bar, the timeline fill, the jump nav active state, the long image disclosure and the lazy video |
| Third party requests on load | zero | zero |
| Cookies | zero | zero |
| Images with explicit dimensions | 100 percent | 100 percent, written at build time from the file on disk |
| Below fold images lazy loaded | 100 percent | 100 percent |

The hero portrait uses `fetchpriority="high"`. Everything else is `loading="lazy"` with
`decoding="async"`.

---

## How the site is built

`build_site.py` generates every page. Content lives in the script, structure in helper functions
(`fig`, `ba`, `scroller`, `metrics`, `callout`, `kv`), and the shell is one function so the sidebar,
footer and meta tags cannot drift between pages. Image dimensions are read off disk with Pillow at
build time, which is why no image can ship without `width` and `height`.

Two validators run after every build:

1. **Static:** em and en dashes, heading hierarchy, one `h1` per page, alt text and dimensions on
   every image, every internal link resolving, every image file present, the anti pattern list, and
   all 21 colour contrast pairs.
2. **Browser,** Chromium via Playwright at 1440, 900 and 390 pixels wide in light and dark: console
   errors, page errors, image decoding, horizontal overflow, focus ring visibility on tab, and that
   the video button creates exactly one `youtube-nocookie` iframe and only after a click.

Both must pass before the site is packaged.

---

## Metadata and the social card

Every page carries a canonical URL and an `og:url` built from its own output path at write time, not
typed by hand, so a page cannot ship somebody else's canonical and a new page gets both for free.

One social card serves the whole site: 1200 by 630, generated from the same tokens and the same
portrait as the site itself, declared with `og:image:width`, `og:image:height` and `og:image:alt`, and
mirrored to `twitter:card` as `summary_large_image`. A portfolio whose only distribution channel is a
link pasted into a profile cannot afford to preview as bare text.

The home page carries `ProfilePage` and `Person` structured data, so a search for the person returns
an entity rather than a document.

---

## Image formats

New images ship as WebP. Existing JPEG covers stay as they are, because rewriting them would change
bytes without changing anything a visitor experiences, and the point of a performance budget is the
visitor rather than the score. Every image, in either format, still carries its own width and height
read off disk at build time.

---

## The notes component

`ul.notes` republishes annotations that were originally written inside a design file as real text
rather than as pixels inside a screenshot. Left rule in the accent, quiet source line beneath in the
mono face.

The reason is not decoration. Text baked into an image is invisible to a screen reader and to a
search engine, and it cannot be selected or quoted. If the reasoning is the valuable part of a
wireframe, it does not belong in the JPEG.

---

## Extending it

- **New project:** add a dict to `PROJECTS`, add a body block, run the build. Card, numbering,
  ordering and previous or next navigation follow automatically.
- **Colour change:** change the token, run the build, read the contrast table. If a pair drops below
  4.5:1, pick a different value rather than shipping it.
- **New component:** document it here first, then add it to the stylesheet. A pattern not in this file
  is not in the system.
