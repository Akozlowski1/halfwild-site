#!/usr/bin/env python3
"""Create a new Field Journal post or event file with the right address and front matter.

Usage:
  python3 tools/new_post.py post  "Title" "Category" [YYYY-MM-DD]
  python3 tools/new_post.py event "Title" YYYY-MM-DDTHH:MM YYYY-MM-DDTHH:MM [venue]
The file is created with draft: true. Write the body in Markdown below the front matter,
put images in static/media/images/, set draft to false, then build.
"""
import datetime, json, os, re, sys
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo('America/Los_Angeles')
def slugify(t): return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', t.lower())).strip('-')
def ms(d): return int(d.timestamp() * 1000)
kind, title = sys.argv[1], sys.argv[2]
slug = slugify(title)
if kind == 'post':
    cat = sys.argv[3]
    day = datetime.datetime.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else datetime.datetime.now()
    day = day.replace(tzinfo=TZ, hour=9, minute=0, second=0, microsecond=0)
    url = f'/field-journal-home/{day.year}/{day.month}/{day.day}/{slug}'
    meta = {'title': title, 'url': url, 'published': ms(day), 'author': 'Andrzej Kozlowski', 'categories': [cat],
            'excerpt': '', 'image': '', 'draft': True}
    path = os.path.join(ROOT, 'content', 'posts', f'{day.year}-{day.month}-{day.day}-{slug}.md')
else:
    start = datetime.datetime.fromisoformat(sys.argv[3]).replace(tzinfo=TZ)
    end = datetime.datetime.fromisoformat(sys.argv[4]).replace(tzinfo=TZ)
    url = f'/new-events/{start.year}/{start.month}/{start.day}/{slug}'
    meta = {'title': title, 'url': url, 'published': ms(datetime.datetime.now(TZ)), 'start': ms(start), 'end': ms(end),
            'venue': sys.argv[5] if len(sys.argv) > 5 else '', 'excerpt': '', 'image': '', 'draft': True}
    path = os.path.join(ROOT, 'content', 'events', f'{start.year}-{start.month}-{start.day}-{slug}.md')
if os.path.exists(path): sys.exit('Already exists: ' + path)
open(path, 'w').write('---\n' + ''.join(f'{k}: {json.dumps(v, ensure_ascii=False)}\n' for k, v in meta.items()) + '---\nWrite here.\n')
print(path); print('Address:', url)
