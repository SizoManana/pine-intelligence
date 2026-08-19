# Your portfolio site

Written for someone who has not done this before. No coding required.
No em dashes anywhere, including in the copy on the pages.

---

## What changed

The site now contains your real work. Every dashed placeholder box is gone, replaced with 82 images
built from your Figma exports and your reporting decks. Your CV and your portrait are in. The design
language is documented in `DESIGN.md`.

```
site/
  index.html                 home: hero, eight project cards, the loop, capabilities, about this page
  about.html                 your story, what you believe, the honest gaps
  DESIGN.md                  the design language, for you or for an AI agent to extend
  README.md                  this file
  robots.txt                 blocks search engines while the site is in progress, delete when ready
  Sizo-Manana-CV.pdf         your CV, already wired to every Download button
  work/
    cambridge.html           Cambridge Commodities quote cockpit
    bso.html                 BSO conversion results
    ruleguard.html           Ruleguard redesign and the strategy documents
    dayshape.html            Dayshape, the true ICP segmentation story
    evara-site.html          Evara rebrand, low fidelity to live, light and dark
    redslim-cpq.html         the CPQ scope calculator
    employmate.html          Employmate redesign
    evara-cpq.html           Evara internal CPQ, the full case study and the walkthrough
  assets/
    css/site.css             one stylesheet for all ten pages, about 21 KB
    img/                     82 images across eight project folders plus your portrait
```

**The one thing to understand:** every page shares `assets/css/site.css`. Change a colour there once
and it changes on all ten pages. You never need to touch styling inside a page file.

---

## Step 1. Look at it

Double click `index.html`. It opens in your browser and works completely offline. Click through all
ten pages. Nothing you do here can break anything and nothing is public yet.

If your computer is set to dark mode you will see the dark version. Switch your system appearance to
light and reload to see the other one. Both were designed.

---

## Step 2. Publish it, about fifteen minutes

You already have the GitHub account, so start at step 2.

1. Click **+** in the top right of GitHub, then **New repository**
2. Name it **exactly** `yourusername.github.io`, using your real username. It must match your
   username exactly, including the `.github.io` part, or this will not work
3. Set it to **Public**. Private repositories cannot use Pages on the free plan
4. Click **Create repository**
5. Click **uploading an existing file**
6. Drag in **everything inside the `site` folder**, not the folder itself. That means `index.html`,
   `about.html`, `DESIGN.md`, `README.md`, `robots.txt`, `Sizo-Manana-CV.pdf`, and the `work` and
   `assets` folders
7. Scroll down, click **Commit changes**
8. Go to **Settings**, then **Pages** in the left sidebar
9. Under **Build and deployment** set Source to **Deploy from a branch**, Branch to **main**, folder
   to **/ (root)**, then **Save**
10. Wait two or three minutes, then visit `https://yourusername.github.io`

### Updating it later

Open the repository, click the file, click the pencil icon to edit in the browser, make your change,
click **Commit changes**. Live in about a minute. To add images use **Add file** then **Upload files**.

### If it does not work

- **404 page:** the repository name almost certainly does not match your username exactly. Check it
  character by character
- **Still 404 after ten minutes:** confirm `index.html` is at the top level of the repository, not
  inside a folder called `site`
- **Changes not showing:** hard refresh with Ctrl+Shift+R, or Cmd+Shift+R on a Mac
- **Images not appearing:** the folder path does not match. Filenames are case sensitive

---

## Step 3. The one thing to remember before you share the link

`robots.txt` currently tells search engines not to index the site:

```
User-agent: *
Disallow: /
```

That is deliberate, so a work in progress does not end up in Google under your name. **It does not
block people.** Anyone you send the link to sees the site normally.

When you are happy with the site, delete `robots.txt` from the repository. Until then, feel free to
send the link to anyone. Just do not expect to find yourself in search results.

---

## Step 4. Put the link everywhere

- LinkedIn **Contact info**, as your website
- LinkedIn **Featured**, as the second item after the CPQ video
- The header of your CV, replacing `[portfolio URL once live]`
- Your email signature
- Every application

---

## Adding a prototype recording later

When you record a walkthrough, send it over and it will be converted to a web optimised MP4 that
plays inline on the case study page, self hosted, muted by default, with a still image fallback.

Not a Figma embed. Embedding a Figma prototype makes the entire underlying file publicly viewable,
including parked frames and internal comments, and it barely works on a phone.

---

## Adding a new project yourself

The site is generated by a script, so the tidy way is to send the new material over and have the
script rebuild. If you want to do it by hand:

1. Copy `work/employmate.html` to a new filename
2. Replace the content between `<main>` and `</main>`
3. On `index.html`, copy one of the `<li><a class="card">` blocks and edit it

Two rules if you edit HTML by hand:

- Inside `work/`, image paths start with `../assets/` because you are one folder deep. On
  `index.html` and `about.html` they start with `assets/`
- **Every image needs `width` and `height` attributes** matching the real file, and real alt text.
  That is not pedantry: it is why the page does not jump while it loads, and you have a WCAG claim
  on your CV that somebody will check

---

## What is still worth doing

1. **Record one prototype walkthrough.** The strongest thing missing.
2. **Write one piece nobody has to approve.** A CRO audit of a public fintech site, or a written
   piece on designing inside HubSpot UI extension constraints. Every case study here belongs to one
   employer. One piece that is entirely yours changes that.
3. **Delete `robots.txt`** when you are ready to be found.
