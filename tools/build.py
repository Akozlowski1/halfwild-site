#!/usr/bin/env python3
"""Build the Half Wild static site.

Usage: python3 tools/build.py            (from the site folder; writes dist/)
Content lives in content/{posts,events,pages}/*.md: a front-matter block (one `key: JSON value`
per line) and a body. Bodies with `format: "html"` are used as is; any other body is Markdown
(paragraphs, # headings, **bold**, *italic*, [links](url), ![images](url), - lists, > quotes,
and a line `[audio: /media/audio/file.mp3 | Title]` for an audio player).
Standard library only.
"""
import datetime, glob, html, json, os, re, shutil, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.environ.get('HW_DIST') or os.path.join(ROOT, 'dist')
CFG = json.load(open(os.path.join(ROOT, 'site.json')))
TZ = ZoneInfo(CFG['timezone'])
ASSETS = json.load(open(os.path.join(ROOT, 'content', 'site-assets.json')))
E = html.escape

# ---------------- content loading ----------------
def load(path):
    raw = open(path, encoding='utf-8').read()
    m = re.match(r'---\n(.*?)\n---\n?(.*)', raw, re.S)
    meta = {}
    for line in m.group(1).splitlines():
        if ': ' in line:
            k, v = line.split(': ', 1)
            try: meta[k.strip()] = json.loads(v)
            except ValueError: meta[k.strip()] = v.strip()
    body = m.group(2)
    meta['html'] = body if meta.get('format') == 'html' else markdown(body)
    meta['file'] = path
    return meta

def markdown(src):
    def inline(t):
        t = E(t, quote=False)
        t = re.sub(r'!\[([^\]]*)\]\(([^)\s]+)\)', r'<img src="\2" alt="\1" loading="lazy">', t)
        t = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', r'<a href="\2">\1</a>', t)
        t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
        t = re.sub(r'(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)', r'<em>\1</em>', t)
        return t
    out = []
    for block in re.split(r'\n\s*\n', src.strip()):
        lines = block.splitlines()
        if not lines: continue
        a = re.match(r'\[audio:\s*([^|\]]+?)\s*(?:\|\s*([^\]]*))?\]$', block.strip())
        if a:
            out.append(f'<figure class="audio"><figcaption>{E(a.group(2) or "")}</figcaption>'
                       f'<audio controls preload="none" src="{E(a.group(1))}"></audio></figure>')
        elif re.match(r'#{1,4} ', lines[0]) and len(lines) == 1:
            n = len(lines[0].split(' ')[0]); out.append(f'<h{n}>{inline(lines[0][n+1:])}</h{n}>')
        elif all(re.match(r'[-*] ', l) for l in lines):
            out.append('<ul>' + ''.join(f'<li>{inline(l[2:])}</li>' for l in lines) + '</ul>')
        elif all(l.startswith('>') for l in lines):
            out.append('<blockquote><p>' + '<br>'.join(inline(l.lstrip('> ')) for l in lines) + '</p></blockquote>')
        elif lines[0].strip() == '---':
            out.append('<hr>')
        elif re.match(r'!\[[^\]]*\]\([^)]+\)$', block.strip()):
            out.append('<figure>' + inline(block.strip()) + '</figure>')
        else:
            out.append('<p>' + '<br>'.join(inline(l) for l in lines) + '</p>')
    return '\n'.join(out)

posts = sorted((load(p) for p in glob.glob(os.path.join(ROOT, 'content/posts/*.md'))), key=lambda x: -x['published'])
posts = [p for p in posts if not p.get('draft')]
events = sorted((load(p) for p in glob.glob(os.path.join(ROOT, 'content/events/*.md'))), key=lambda x: -x['start'])
events = [e for e in events if not e.get('draft')]
pages = {p['url']: p for p in (load(f) for f in glob.glob(os.path.join(ROOT, 'content/pages/*.md')))}
comments = {}
for f in glob.glob(os.path.join(ROOT, 'content/comments/*.json')):
    c = json.load(open(f)); comments[c['post']] = c['comments']

def dt(ms): return datetime.datetime.fromtimestamp(ms / 1000, TZ)
def long_date(ms): d = dt(ms); return f'{d:%B} {d.day}, {d.year}'
def short_date(ms): d = dt(ms); return f'{d.month}/{d.day}/{d:%y}'
def base_name(path): return re.sub(r'^[0-9a-f]{6}-', '', os.path.basename(path)).rsplit('.', 1)[0].lower()
def month_day(ms): d = dt(ms); return f'{d:%B} {d.day}'
def clock(ms): d = dt(ms); return f'{d.hour % 12 or 12}:{d:%M} {"AM" if d.hour < 12 else "PM"}'
def audio_url(h):
    base = CFG.get('audio_base_url') or ''
    return h.replace('src="/media/audio/', f'src="{base}/media/audio/') if base else h

# ---------------- templates ----------------
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Amatic+SC:wght@400;700&family=Figtree:wght@500;600&family=Quicksand:wght@300;400&display=swap" rel="stylesheet">')

def nav_html(active):
    items = []
    for n in CFG['nav']:
        on = ' class="active"' if active == n['url'] or any(active == c['url'] for c in n.get('children', [])) else ''
        if n.get('children'):
            sub = ''.join(f'<li><a href="{c["url"]}">{E(c["title"])}</a></li>' for c in n['children'])
            items.append(f'<li class="folder"><a href="{n["url"]}"{on}>{E(n["title"])}</a><ul>{sub}</ul></li>')
        else:
            items.append(f'<li><a href="{n["url"]}"{on}>{E(n["title"])}</a></li>')
    mobile = []
    for n in CFG['nav']:
        for c in n.get('children') or [n]:
            mobile.append(f'<li><a href="{c["url"]}">{E(c["title"])}</a></li>')
    return (f'<nav class="nav" aria-label="Main"><ul>{"".join(items)}</ul></nav>'
            f'<details class="burger"><summary aria-label="Menu"><span></span><span></span><span></span></summary>'
            f'<ul>{"".join(mobile)}</ul></details>')

ICONS = {'Facebook': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 21v-7.5H16l.4-3h-2.9V8.6c0-.9.3-1.5 1.5-1.5h1.5V4.4c-.3 0-1.2-.1-2.2-.1-2.2 0-3.7 1.3-3.7 3.8v2.4H8.2v3h2.4V21z"/></svg>',
         'Instagram': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 7.3A4.7 4.7 0 1 0 12 16.7 4.7 4.7 0 0 0 12 7.3zm0 7.7a3 3 0 1 1 0-6 3 3 0 0 1 0 6zm4.9-8.9a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2zM20.9 7.6c-.1-1.5-.4-2.8-1.5-3.9S17 2.2 15.5 2.1c-1.5-.1-6-.1-7.5 0-1.5.1-2.8.4-3.9 1.5S2.7 6.1 2.6 7.6c-.1 1.5-.1 6 0 7.5.1 1.5.4 2.8 1.5 3.9s2.4 1.4 3.9 1.5c1.5.1 6 .1 7.5 0 1.5-.1 2.8-.4 3.9-1.5s1.4-2.4 1.5-3.9c.1-1.5.1-6 0-7.5z" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>'}

def layout(title, body, url, active='', banner=None, description=None, image=None, noindex=False, extra_head=''):
    full_title = f'{title} — {CFG["title"]}' if title and title != CFG['title'] else CFG['title']
    full_title = full_title.replace(' — ', ' | ')
    desc = description or CFG['description']
    canon = CFG['base_url'] + (url if url != '/' else '')
    og_img = CFG['base_url'] + (image or ASSETS['banner'])
    ban = f'<div class="banner" style="background-image:url(\'{E(banner)}\')"></div>' if banner else ''
    social = ''.join(f'<a href="{s["url"]}" aria-label="{s["name"]}" class="icon">{ICONS.get(s["name"], "")}</a>' for s in CFG['social'])
    flinks = ''.join(f'<a href="{l["url"]}">{E(l["title"])}</a>' for l in CFG['footer_links'])
    robots = '<meta name="robots" content="noindex">' if noindex else ''
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(full_title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{canon}">{robots}
<meta property="og:title" content="{E(title or CFG['title'])}"><meta property="og:description" content="{E(desc)}"><meta property="og:image" content="{E(og_img)}"><meta property="og:url" content="{canon}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{ASSETS.get('favicon') or ASSETS['logo']}"><link rel="alternate" type="application/rss+xml" title="Half Wild Field Journal" href="/feed.xml">
{FONTS}<link rel="stylesheet" href="/assets/site.css">{extra_head}</head>
<body class="{'has-banner' if banner else 'no-banner'}">
<header class="site-header"><a class="logo" href="/"><img src="{ASSETS['logo']}" alt="Half Wild"></a>{nav_html(active)}</header>
{ban}<main>{body}</main>
<footer class="site-footer"><div class="social">{social}</div><div class="flinks">{flinks}</div></footer>
</body></html>'''

def card(p):
    cats = p.get('categories') or []
    catlinks = ', '.join(f'<a href="{CFG["category_pages"].get(c, "/")}">{E(c)}</a>' for c in cats)
    img = f'<a class="thumb" href="{p["url"]}"><img src="{p["image"]}" alt="" loading="lazy"></a>' if p.get('image') else ''
    meta = (catlinks + ' <span class="dot">•</span> ' if catlinks else '') + f'<time>{short_date(p["published"])}</time>'
    return (f'<article class="card">{img}<div class="meta">{meta}</div>'
            f'<h2 class="card-title"><a href="{p["url"]}">{E(p["title"])}</a></h2>'
            f'<p class="excerpt">{E(p.get("excerpt", ""))}</p><a class="more" href="{p["url"]}">Read More</a></article>')

def grid(items): return '<section class="grid">' + ''.join(card(p) for p in items) + '</section>'

def prevnext(items, i, label_fn):
    out = '<nav class="pager">'
    if i + 1 < len(items):
        o = items[i + 1]; out += f'<a class="prev" href="{o["url"]}"><span class="pdate">{label_fn(o)}</span><span class="ptitle">{E(o["title"])}</span></a>'
    else: out += '<span></span>'
    if i > 0:
        o = items[i - 1]; out += f'<a class="next" href="{o["url"]}"><span class="pdate">{label_fn(o)}</span><span class="ptitle">{E(o["title"])}</span></a>'
    return out + '</nav>'

def comments_html(url):
    cs = comments.get(url)
    if not cs: return ''
    rows = ''.join(f'<li class="depth{c.get("depth", 0)}"><div class="cmeta"><strong>{E(c["name"] or "Anonymous")}</strong> <time>{long_date(c["date"])}</time></div>{c["body"]}</li>' for c in sorted(cs, key=lambda c: -c['date']))
    return f'<section class="comments"><h2>Comments ({len(cs)})</h2><ul>{rows}</ul><p class="note">Comments are closed. These were left on the earlier version of this site.</p></section>'

# ---------------- writing ----------------
written = []
def write(url, text):
    path = os.path.join(DIST, url.strip('/'), 'index.html') if url not in ('/404',) else os.path.join(DIST, '404.html')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, 'w', encoding='utf-8').write(text)
    written.append(url)

def build():
    if os.path.isdir(DIST): shutil.rmtree(DIST)
    os.makedirs(DIST)
    # static assets
    for src in ('static', 'assets'):
        s = os.path.join(ROOT, src)
        if os.path.isdir(s):
            shutil.copytree(s, DIST if src == 'static' else os.path.join(DIST, 'assets'), dirs_exist_ok=True)
    if CFG.get('audio_base_url'):
        shutil.rmtree(os.path.join(DIST, 'media', 'audio'), ignore_errors=True)

    # home (Field Journal)
    write('/', layout('', grid(posts), '/', '/', banner=ASSETS['banner']))

    # posts
    for i, p in enumerate(posts):
        cats = ' '.join(f'<a href="{CFG["category_pages"].get(c, "/")}">{E(c)}</a>' for c in p.get('categories') or [])
        body = (f'<article class="post"><header class="post-head"><div class="meta"><time>{long_date(p["published"])}</time>'
                f'{" <span class=dot>•</span> " + cats if cats else ""}</div><h1>{E(p["title"])}</h1>'
                f'<div class="byline">{E(p.get("author") or "")}</div></header>'
                f'<div class="body">{audio_url(p["html"])}</div>{comments_html(p["url"])}'
                f'{prevnext(posts, i, lambda o: long_date(o["published"]))}</article>')
        write(p['url'], layout(p['title'], body, p['url'], '/', description=p.get('excerpt'), image=p.get('image')))

    # category pages
    for cat, url in CFG['category_pages'].items():
        pg = pages.get(url, {'title': cat, 'html': f'<h1>{E(cat)}</h1>'})
        items = [p for p in posts if cat in (p.get('categories') or [])]
        lst = grid(items) if items else '<p class="empty">New pieces are on the way.</p>'
        write(url, layout(pg['title'], f'<div class="intro">{pg["html"]}</div>{lst}', url, url, banner=pg.get('banner'), description=pg.get('description')))

    # events list
    rows = []
    now = datetime.datetime.now(TZ).timestamp() * 1000
    for e in events:
        d = dt(e['start'])
        img = f'<a class="ev-thumb" href="{e["url"]}"><img src="{e["image"]}" alt="" loading="lazy"><span class="datetag"><b>{d:%b}</b><i>{d.day}</i></span></a>' if e.get('image') else ''
        where = E(', '.join(x for x in (e.get('venue'), e.get('address')) if x))
        rows.append(f'<article class="ev">{img}<div class="ev-text"><h2><a href="{e["url"]}">{E(e["title"])}</a></h2>'
                    f'<p class="when">{long_date(e["start"])}, {clock(e["start"])} – {clock(e["end"])}</p>'
                    f'{f"<p class=where>{where}</p>" if where else ""}<a class="btn" href="{e["url"]}">View Event →</a></div></article>')
    write('/new-events', layout('Events', '<section class="events">' + ''.join(rows) + '</section>', '/new-events', '/new-events', banner=ASSETS['banner']))

    # event pages
    for i, e in enumerate(events):
        d = dt(e['start'])
        where = E(', '.join(x for x in (e.get('venue'), e.get('address')) if x))
        img = f'<img class="ev-hero" src="{e["image"]}" alt="">' if e.get('image') else ''
        if e.get('image') and base_name(e['image']) in {base_name(x) for x in re.findall(r'<img src="([^"]+)"', e['html'][:3000])}:
            img = ''  # the body already opens with the same picture
        body = (f'<article class="event"><a class="back" href="/new-events">← Back to All Events</a><div class="ev-grid">'
                f'<aside><h1>{E(e["title"])}</h1><p class="when">{d:%A}, {d:%B} {d.day}, {d.year}<br>{clock(e["start"])} – {clock(e["end"])}</p>'
                f'{f"<p class=where>{where}</p>" if where else ""}</aside><div class="body">{img}{audio_url(e["html"])}</div></div>'
                f'{prevnext(events, i, lambda o: month_day(o["start"]))}</article>')
        write(e['url'], layout(e['title'], body, e['url'], '/new-events', description=e.get('excerpt'), image=e.get('image')))

    # standalone pages
    for url, pg in pages.items():
        if url in CFG['category_pages'].values(): continue
        h = pg['html']
        if '[[form]]' in h:
            h = h.replace('<p>[[form]]</p>', form_html(url)).replace('[[form]]', form_html(url))
        write(url, layout(pg['title'], f'<div class="page">{h}</div>', url, url, banner=pg.get('banner'),
                          description=pg.get('description'), noindex=url in CFG['unlisted_pages']))

    write('/404', layout('Page not found', '<div class="page"><h1>Page not found</h1><p>That page is not here. Try the <a href="/">Field Journal</a> or <a href="/new-events">Events</a>.</p></div>', '/404'))
    extras()

def form_html(url):
    f = CFG['forms']
    if url == '/subscribe':
        if f.get('subscribe_embed_html'): return f['subscribe_embed_html']
        return '<p class="pending">[Subscribe form: the Mailchimp signup form goes here once its embed code is added to site.json.]</p>'
    if url == '/contact':
        if f.get('contact_action'):
            return (f'<form class="form" method="post" action="{E(f["contact_action"])}">'
                    '<label>Name<input name="name" required autocomplete="name"></label>'
                    '<label>Email Address<input type="email" name="email" required autocomplete="email"></label>'
                    '<label>Subject<input name="subject" required></label>'
                    '<label>Message<textarea name="message" rows="7" required></textarea></label>'
                    '<button type="submit">Submit</button></form>')
        return '<p class="pending">[Contact form: needs a form handler; see site.json "contact_action".]</p>'
    return ''

def extras():
    # sitemap
    urls = ['/'] + [p['url'] for p in posts] + ['/new-events'] + [e['url'] for e in events] + \
           [u for u in list(CFG['category_pages'].values()) + list(pages) if u not in CFG['unlisted_pages']]
    seen = []
    for u in urls:
        if u not in seen: seen.append(u)
    sm = ''.join(f'<url><loc>{CFG["base_url"]}{"" if u == "/" else u}</loc></url>' for u in seen)
    open(os.path.join(DIST, 'sitemap.xml'), 'w').write(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n')
    open(os.path.join(DIST, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: {CFG["base_url"]}/sitemap.xml\n')
    # RSS
    def rfc(ms): return dt(ms).strftime('%a, %d %b %Y %H:%M:%S %z')
    items = ''.join(f'<item><title>{E(p["title"])}</title><link>{CFG["base_url"]}{p["url"]}</link><guid>{CFG["base_url"]}{p["url"]}</guid>'
                    f'<pubDate>{rfc(p["published"])}</pubDate><description>{E(p.get("excerpt", ""))}</description></item>' for p in posts[:20])
    open(os.path.join(DIST, 'feed.xml'), 'w').write(f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Half Wild Field Journal</title>'
                                                   f'<link>{CFG["base_url"]}/</link><description>{E(CFG["description"])}</description>{items}</channel></rss>\n')
    # redirects: _redirects for Cloudflare Pages, plus small HTML redirect pages so the same
    # build also works on hosts without server-side redirects (GitHub Pages)
    import urllib.parse
    shutil.copyfile(os.path.join(ROOT, 'redirects.txt'), os.path.join(DIST, '_redirects'))
    rules = []
    for line in open(os.path.join(ROOT, 'redirects.txt')):
        parts = line.split()
        if len(parts) >= 2 and not line.startswith('#'): rules.append((parts[0], parts[1]))
    stubs = []
    for src, dst in rules:
        if src.endswith('/*'):
            base = src[:-2]
            if dst.endswith(':splat'):
                for p in posts:  # known old addresses for each post under that prefix
                    rest = p['url'].split('/', 2)[2]
                    stubs.append((base + '/' + rest, dst.replace(':splat', rest)))
            continue
        stubs.append((src, dst))
    for src, dst in stubs:
        path = os.path.join(DIST, urllib.parse.unquote_plus(src).strip('/'), 'index.html')
        if os.path.exists(path) or src.strip('/') == '': continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'w').write(f'<!doctype html><meta charset="utf-8"><title>Redirecting</title><link rel="canonical" href="{CFG["base_url"]}{dst}">'
                              f'<meta name="robots" content="noindex"><meta http-equiv="refresh" content="0; url={dst}"><a href="{dst}">Continue</a>')

def apply_base_path():
    """Staging only: when the site is served from a sub-folder (e.g. user.github.io/halfwild-site),
    prefix every root-relative link with HW_BASE. Unset for the live domain."""
    base = os.environ.get('HW_BASE', '').rstrip('/')
    if not base: return
    for f in glob.glob(os.path.join(DIST, '**', '*.html'), recursive=True):
        t = open(f, encoding='utf-8').read()
        t = re.sub(r'(href|src|action)="/(?!/)', lambda m: f'{m.group(1)}="{base}/', t)
        t = re.sub(r"url\('/(?!/)", f"url('{base}/", t)
        t = t.replace('content="0; url=/', f'content="0; url={base}/')
        open(f, 'w', encoding='utf-8').write(t)

if __name__ == '__main__':
    build()
    apply_base_path()
    print(f'built {len(written)} pages into {DIST}')
