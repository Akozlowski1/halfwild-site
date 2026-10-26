# Half Wild website (static)

Replacement for the Squarespace site at halfwild.earth. Built 2026-10-26. Not yet live.

## How it works
- `content/posts/`, `content/events/`, `content/pages/`: one file per post, event or page. Each starts with a short block of settings (title, address, date, categories, image), then the text.
- The 41 imported Squarespace items keep their original HTML (`format: "html"`). New posts are written in plain Markdown.
- `content/comments/`: the 11 reader comments from Squarespace, shown read-only under their posts.
- `static/media/`: images (display copies, at most 2,000 pixels wide) and audio. Full archive copies are in `Half Wild/Archive/`.
- `site.json`: menu, footer, social links, form settings.
- `assets/site.css`: the design (charcoal page, teal Amatic SC titles, Georgia text, tan navigation).
- `redirects.txt`: old Squarespace addresses that change, and where they now point.
- `tools/build.py`: turns all of the above into the finished site in `dist/`. Python 3 only, no other software.
- `tools/new_post.py`: starts a new post or event file with the correct address.
- `tools/import_squarespace.py`: the one-time import. Already run; it refuses to run again unless given `--force`, because that would overwrite later edits.

## Publishing a new post (what Claude does when asked)
1. `python3 tools/new_post.py post "Title" "Essays & Field Notes" 2026-11-02`
2. Write the text in Markdown under the settings block; add images to `static/media/images/` and audio to `static/media/audio/`; fill in `excerpt` and `image`; set `draft` to `false`.
3. `python3 tools/build.py` and check the page locally.
4. Commit and push. The host rebuilds and publishes automatically.

Addresses follow the Squarespace pattern `/field-journal-home/YYYY/M/D/slug` and `/new-events/YYYY/M/D/slug`.

## Hosting
Works on either free host:
- GitHub Pages: uses `.github/workflows/pages.yml`; redirects are served as small redirect pages.
- Cloudflare Pages: build command `python3 tools/build.py`, output folder `dist`; redirects come from `_redirects`. Limit: no single file over 25 MiB, which five of the long recordings exceed.

## Open items (see the strategic plan)
- Contact form needs a handler (`site.json` → `forms.contact_action`). Until then the page shows a placeholder.
- Subscribe needs the Mailchimp embed code (`site.json` → `forms.subscribe_embed_html`).
- Fonts: Omnes Pro and Proxima Nova (Adobe fonts licensed through Squarespace) replaced by the free Quicksand Light and Figtree, chosen 2026-10-26 by side-by-side comparison. Body text is Georgia, as on Squarespace.
