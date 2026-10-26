#!/usr/bin/env python3
"""One-time import: Squarespace archive -> site/content and site/static/media.

Usage: python3 import_squarespace.py <archive_dir> <site_dir>
Reads the raw JSON/HTML saved in Phase 0 and the media manifest, cleans Squarespace's
block HTML down to plain semantic HTML, rewrites media links to local files, and writes
one file per post, event and page. Re-running overwrites the generated files.
"""
import csv, glob, html, json, os, re, shutil, sys, urllib.parse
from html.parser import HTMLParser

ARCH, SITE = sys.argv[1], sys.argv[2]
if os.path.exists(os.path.join(SITE, 'content', 'IMPORTED')) and '--force' not in sys.argv:
    sys.exit('Content was already imported and may have been edited since. Re-run with --force to overwrite it.')
RAW = os.path.join(ARCH, '_raw')
MEDIA_OUT = os.path.join(SITE, 'static', 'media')
MAX_W = 2000  # display copies; full archive copies stay in Half Wild/Archive

# ---------- media map: remote URL (no query) -> local site path ----------
manifest = list(csv.DictReader(open(os.path.join(ARCH, 'MEDIA-MANIFEST.csv'))))
by_url = {r['original_address'].split('?')[0]: r for r in manifest}
used_media = {}

def norm(u):
    if not u: return u
    u = html.unescape(u.strip())
    if u.startswith('//'): u = 'https:' + u
    return u.split('?')[0] if ('squarespace' in u) else u

def local_media(u):
    """Return the site path for a remote media URL, registering it for copying."""
    key = norm(u)
    r = by_url.get(key)
    if not r:
        # same asset under another encoding
        for k, v in by_url.items():
            if urllib.parse.unquote(k) == urllib.parse.unquote(key):
                r = v; break
    if not r or not r['local_file']:
        return u
    src = os.path.join(ARCH, r['local_file'])
    name = os.path.basename(r['local_file'])
    sub = 'audio' if r['kind'] == 'audio' else 'images'
    used_media[src] = (sub, name)
    if name.lower().endswith('.ico'): return f'/media/{sub}/{name}'
    return f'/media/{sub}/{name}'

# ---------- HTML cleaner ----------
VOID = {'img', 'br', 'hr', 'input', 'source', 'meta', 'link', 'wbr', 'col', 'area', 'base', 'embed', 'param', 'track'}
KEEP = {'p', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'em', 'strong', 'i', 'b', 'u', 's', 'ul', 'ol', 'li',
        'blockquote', 'figure', 'figcaption', 'hr', 'sup', 'sub', 'pre', 'code', 'audio', 'source', 'img', 'table',
        'thead', 'tbody', 'tr', 'td', 'th', 'iframe'}
DROP = {'style', 'script', 'noscript', 'svg', 'button', 'form', 'template', 'select', 'textarea', 'label'}

class Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []; self.stack = []; self.skip = 0
    def emit(self, s): self.out.append(s)
    def handle_starttag(self, t, attrs):
        a = dict(attrs); cls = a.get('class', '') or ''
        if self.skip:
            if t not in VOID: self.skip += 1
            return
        if t in DROP or 'image-caption-wrapper' in cls and not self._has_caption:
            pass
        if t in DROP:
            if t not in VOID: self.skip = 1
            return
        if 'sqs-audio-embed' in cls:
            src = a.get('data-asset-url') or a.get('data-url')
            title = a.get('data-title') or ''
            if src:
                self.emit(f'<figure class="audio"><figcaption>{html.escape(title)}</figcaption>'
                          f'<audio controls preload="none" src="{html.escape(local_media(src))}"></audio></figure>')
            self.skip = 1
            return
        if t == 'div':
            if re.search(r'\brow\b', cls) and 'sqs-row' in cls or cls.strip().startswith('row'):
                self.emit('<div class="row">'); self.stack.append('div'); return
            m = re.search(r'\bspan-(\d+)\b', cls)
            if 'col' in cls.split() and m:
                self.emit(f'<div class="col c{m.group(1)}">'); self.stack.append('div'); return
            self.stack.append(None); return
        if t == 'img':
            src = a.get('data-src') or a.get('data-image') or a.get('src')
            if not src: return
            alt = html.escape(a.get('alt', '') or '')
            dims = a.get('data-image-dimensions') or ''
            wh = ''
            if re.match(r'\d+x\d+$', dims):
                w, h = dims.split('x'); wh = f' width="{w}" height="{h}"'
            self.emit(f'<img src="{html.escape(local_media(src))}" alt="{alt}"{wh} loading="lazy">')
            return
        if t == 'a':
            href = a.get('href', '')
            href = re.sub(r'^https?://(www\.)?halfwild\.earth', '', href) or '/'
            href = re.sub(r'^/(songs|blog)/(\d{4}/)', r'/field-journal-home/\2', href)  # old collection slugs, dead on Squarespace too
            extra = ' class="button"' if 'button' in cls else ''
            tgt = ' target="_blank" rel="noopener"' if a.get('target') == '_blank' else ''
            self.emit(f'<a href="{html.escape(href)}"{extra}{tgt}>'); self.stack.append('a'); return
        if t in ('audio', 'source'):
            src = a.get('src')
            s = f' src="{html.escape(local_media(src))}"' if src else ''
            if t == 'audio':
                self.emit(f'<audio controls preload="none"{s}>'); self.stack.append('audio')
            else:
                self.emit(f'<source{s}>')
            return
        if t == 'iframe':
            src = a.get('src') or a.get('data-src') or ''
            self.emit(f'<iframe src="{html.escape(src)}" loading="lazy" allowfullscreen></iframe>'); self.stack.append('iframe'); return
        if t == 'span':
            if 'text-color--accent' in cls:
                self.emit('<span class="accent">'); self.stack.append('span'); return
            self.stack.append(None); return
        if t in KEEP:
            if t in VOID: self.emit(f'<{t}>'); return
            classes = []
            st = (a.get('style') or '').replace(' ', '')
            m = re.search(r'text-align:(center|right)', st) or re.search(r'text-align--(center|right)', cls)
            if m and t in ('p', 'h1', 'h2', 'h3', 'h4', 'blockquote', 'figcaption'): classes.append(m.group(1))
            if 'sqsrte-large' in cls: classes.append('large')
            if 'sqsrte-small' in cls: classes.append('small')
            c = f' class="{" ".join(classes)}"' if classes else ''
            self.emit(f'<{t}{c}>'); self.stack.append(t); return
        if t not in VOID: self.stack.append(None)
    _has_caption = True
    def handle_startendtag(self, t, attrs):
        self.handle_starttag(t, attrs)
        if self.skip and t not in VOID: self.skip -= 1
        elif not self.skip and t not in VOID and self.stack:
            x = self.stack.pop()
            if x: self.emit(f'</{x}>')
    def handle_endtag(self, t):
        if t in VOID: return
        if self.skip:
            self.skip -= 1; return
        if self.stack:
            x = self.stack.pop()
            if x: self.emit(f'</{x}>')
    def handle_data(self, d):
        if not self.skip: self.emit(html.escape(d, quote=False))

def clean(h):
    c = Cleaner(); c.feed(h or ''); c.close()
    s = ''.join(c.out)
    s = re.sub(r'<figcaption>\s*</figcaption>', '', s)
    s = re.sub(r'<(p|figure|div class="col c\d+"|div class="row"|a href="[^"]*")>\s*</(p|figure|div|a)>', '', s)
    for _ in range(3):
        s = re.sub(r'<div class="col c\d+">\s*</div>', '', s)
        s = re.sub(r'<div class="row">\s*</div>', '', s)
    s = re.sub(r'[ \t]*\n[ \t\n]*', '\n', s)
    return s.strip()

def text(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h or ''))).strip()

def fm_dump(d, body):
    return '---\n' + ''.join(f'{k}: {json.dumps(v, ensure_ascii=False)}\n' for k, v in d.items() if v not in (None, '', [])) + '---\n' + body + '\n'

# ---------- posts and events ----------
os.makedirs(SITE + '/content/posts', exist_ok=True); os.makedirs(SITE + '/content/events', exist_ok=True)
os.makedirs(SITE + '/content/pages', exist_ok=True); os.makedirs(SITE + '/content/comments', exist_ok=True)
count = {'posts': 0, 'events': 0, 'pages': 0}
for f in sorted(glob.glob(RAW + '/json/*.json')):
    d = json.load(open(f)); it = d.get('item')
    if not it: continue
    full = it.get('fullUrl', '')
    if full.startswith('/field-journal-home/'): kind = 'posts'
    elif full.startswith('/new-events/'): kind = 'events'
    else: continue
    meta = {
        'title': html.unescape(it['title']),
        'url': full,
        'published': int(it['publishOn']),
        'author': (it.get('author') or {}).get('displayName') or 'Andrzej Kozlowski',
        'categories': it.get('categories') or [],
        'tags': it.get('tags') or [],
        'excerpt': text(it.get('excerpt')),
        'image': local_media(it['assetUrl']) if it.get('assetUrl') else None,
        'format': 'html',
        'source': 'squarespace:' + it['id'],
    }
    if kind == 'events':
        meta['start'] = int(it['startDate']); meta['end'] = int(it['endDate'])
        loc = it.get('location') or {}
        meta['venue'] = loc.get('addressTitle'); meta['address'] = ', '.join(x for x in (loc.get('addressLine1'), loc.get('addressLine2')) if x)
    body = clean(it.get('body'))
    slug = full.rstrip('/').split('/')[-1]
    datepart = '-'.join(full.strip('/').split('/')[1:4])
    open(f'{SITE}/content/{kind}/{datepart}-{slug}.md', 'w').write(fm_dump(meta, body))
    count[kind] += 1

# ---------- standalone pages (rendered HTML <main>, not the stale JSON field) ----------
PAGES = ['about', 'contact', 'subscribe', 'for-contributors', 'editorial-circle', 'editorial-circle1',
         'essays-field-notes', 'conversations', 'songs-soundscapes', 'profiles-portraits', 'home-alt-bedford']
for n in PAGES:
    d = json.load(open(f'{RAW}/json/{n}.json')); c = d['collection']
    t = open(f'{RAW}/html/{n}.html', errors='replace').read()
    main = re.search(r'<main.*?</main>', t, re.S).group(0)
    # cut summary blocks (post grids are generated) and form blocks (rebuilt)
    main = re.sub(r'<div class="sqs-block[^"]*summary-block.*?(?=<div class="sqs-block |</main>)', '', main, flags=re.S)
    main = re.sub(r'<div class="sqs-block[^"]*form-block.*?(?=<div class="sqs-block |</main>)', '<p>[[form]]</p>', main, flags=re.S)
    body = clean(main)
    m = re.match(r'\s*(?:<[^>]+>\s*)*?<img src="([^"]+)"[^>]*>', body)
    banner = None
    if m and body.find('<img') < 200:
        banner = m.group(1); body = body.replace(m.group(0), re.sub(r'<img[^>]*>', '', m.group(0)), 1)
    seo = c.get('seoData') or {}
    meta = {'title': c.get('title'), 'url': '/' + c.get('urlId', n), 'banner': banner,
            'description': seo.get('seoDescription'), 'format': 'html', 'source': 'squarespace:' + c.get('id', '')}
    open(f'{SITE}/content/pages/{n}.md', 'w').write(fm_dump(meta, body))
    count['pages'] += 1

# site-wide assets
web = json.load(open(RAW + '/json/home.json'))['website']
logo = local_media(web.get('logoImageUrl', ''))
whale = None
for r in manifest:
    if r['filename'] == 'Whale+smaller.png' and '/field-journal-home (page html)' in r['used_in']:
        whale = local_media(r['original_address'])

# comments
for f in glob.glob(ARCH + '/comments/*.json'):
    c = json.load(open(f))
    keep = [{'name': x.get('authorName'), 'url': x.get('authorUrl'), 'date': x.get('addedOn'), 'body': clean(x.get('body')),
             'depth': x.get('depth', 0)} for x in c['comments']]
    json.dump({'post': c['post'], 'comments': keep}, open(f'{SITE}/content/comments/{os.path.basename(f)}', 'w'), indent=1)

# ---------- copy media (images resized for display) ----------
fav = local_media('https://images.squarespace-cdn.com/content/v1/59a1baee893fc05119122dad/430dd403-3dcd-4b41-a9d4-60c19eed4843/favicon.ico')
from PIL import Image, ImageOps
for src, (sub, name) in used_media.items():
    dst_dir = os.path.join(MEDIA_OUT, sub); os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, name)
    if os.path.exists(dst) and os.path.getsize(dst) > 0: continue
    if sub == 'images':
        try:
            im = Image.open(src)
            if im.width > MAX_W:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((MAX_W, MAX_W * 10))
                if im.format == 'JPEG' or name.lower().endswith(('.jpg', '.jpeg')):
                    im.convert('RGB').save(dst, 'JPEG', quality=85, progressive=True, optimize=True); continue
                im.save(dst, optimize=True); continue
        except Exception as e:
            print('resize skipped', name, e)
    shutil.copyfile(src, dst)

json.dump({'logo': logo, 'banner': whale, 'favicon': fav}, open(SITE + '/content/site-assets.json', 'w'), indent=1)
open(os.path.join(SITE, 'content', 'IMPORTED'), 'w').write('Imported from the Squarespace archive on 2026-10-26. Files in content/ are now the source of truth; edit them directly.\n')
print(count, 'media files used:', len(used_media))
