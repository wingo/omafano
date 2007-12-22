from mod_python import apache

import os
import os.path
import time
import urllib
from pysqlite2 import dbapi2
import Image
import EXIF

########################################################################
## Configuration

BASE_URI=None
PHOTOS_RELPATH=''

########################################################################
## Utils

# from Django -- thanks. to be honest i have no idea why this is necessary
def smart_str(s, encoding='utf-8', errors='strict'):
    # Returns a bytestring version of 's', encoded as specified in 'encoding'.
    if not isinstance(s, basestring):
        try:
            return str(s)
        except UnicodeEncodeError:
            return unicode(s).encode(encoding, errors)
    elif isinstance(s, unicode):
        return s.encode(encoding, errors)
    elif s and encoding != 'utf-8':
        return s.decode('utf-8', errors).encode(encoding, errors)
    else:
        return s

# my own ghetto sxml foo
def html2str(expr):
    if not isinstance(expr, list):
        return smart_str(expr)
    operator = expr[0]
    args = [html2str(arg) for arg in expr[1:]]
    return smart_str(operator(args))
class html:
    def __getattr__(self, attr):
        def _trans(k):
            table = {'klass': 'class'}
            return table.get(k, k)
        def tag(*targs, **kw):
            def render(args):
                return ('<%s%s>%s</%s>'
                        % (attr,
                           ''.join([' %s="%s"' % (_trans(k), v)
                                    for k, v in kw.items()]),
                           '\n'.join(args),
                           attr))
            if targs:
                return render(targs[0])
            else:
                return render
        # this only works with python2.4
        # tag.__name__ = attr 
        return tag
html = html()

########################################################################
# URLs

def q(s):
    return urllib.quote_plus(smart_str(s))
def relurl(url):
    return BASE_URI + url
def nested_a_head(url, kw={}):
    return html.a(href=relurl('index.py/' + url), **kw)
def photo_a_head(id, tag=None, **kw):
    return nested_a_head('photos/%d%s' % (id, tag and '?tag=%s'%q(tag) or ''),
                         kw)
def photourl(relpath):
    return relurl(PHOTOS_RELPATH + '/' + relpath)
def jpg_a_head(id, tag=None, **kw):
    return nested_a_head('photos/%d%s' % (id, tag and '?tag=%s'%q(tag) or ''),
                         kw)
def roll_a_head(id, **kw):
    return nested_a_head('rolls/%d' % (id,), kw)
def rolls_a_head(before=None, after=None, **kw):
    return nested_a_head('rolls/' + (before and '?before=%d'%before or '')
                         + (after and '?after=%d'%after or ''), kw)

def top_link_elt(text='Photo Gallery', **kw):
    return [html.a(href=BASE_URI, **kw), text]
def tag_link_elt(tag=None, **kw):
    return [nested_a_head('tags/' + (tag and q(tag) or ''), kw), tag]
def tags_link_elt(text='Tags', **kw):
    return [nested_a_head('tags/', kw), text]
def thumb_link_elt(photo_id, tag, thumb_relpath, *extra_content):
    return [photo_a_head(photo_id, tag=tag),
            [html.img(src=photourl(thumb_relpath))] + list(extra_content)]


########################################################################
## Parts of pages

def roll_summary(roll_id, roll_time):
    out = [html.div(klass='roll')]
    tagpara = [html.p,
               display_random_thumbs(7, roll_id=roll_id),
               [roll_a_head(roll_id, klass='roll-title',
                            style='text-decoration: none; font-weight: bold;'),
                time.strftime('%d %b %y', time.gmtime(roll_time))],
               [html.br]]

    sql = ('select distinct t.name from photo_tags pt, tags t, photos p'
           '       where t.id=pt.tag_id and p.id=pt.photo_id'
           '       and p.roll_id = ?')
    cur = cxn.cursor()
    cur.execute(sql, (roll_id,))
    words = cur.fetchall()
    for word, in words:
        # fixme: link to only roll
        tagpara.append(tag_link_elt(word, style='text-decoration: none'))
    out.append(tagpara)
    return out
    
def latest_rolls(limit=1):
    cur = cxn.cursor()
    sql = 'select id, time from rolls order by time desc limit ?'
    cur.execute(sql, (limit,))
    res = cur.fetchall()
    return ([html.div(id='latest-rolls')]
            + [roll_summary(roll_id, time) for roll_id, time in res])
           
def make_tag_cloud(*containing_tags, **kwargs):
    roll_id = kwargs.get('roll_id', None)
    thresh = kwargs.get('thresh', 3)
    limit = kwargs.get('limit', 100)
    sql = ('select count(pt.photo_id), t.name'
           '       from photo_tags pt, tags t')
    args = []
    if roll_id is not None:
        sql += ', photos p'
    sql += ' where t.id=pt.tag_id'
    if roll_id is not None:
        sql += ' and pt.photo_id=p.id and p.roll_id=?'
        args.append(roll_id)
    if containing_tags:
        sql += (' and pt.photo_id in'
                '     (select distinct pt.photo_id from'
                '      tags t, photo_tags pt'
                '      where t.id=pt.tag_id and (0')
        for tag in containing_tags:
           sql += ' or t.name=?'
        sql += '))'
        for tag in containing_tags:
           sql += ' and t.name!=?'
        args.extend(containing_tags + containing_tags)
    sql += ' group by t.name'
    cur = cxn.cursor()
    cur.execute(sql, args)
    out = [html.div(id='tagcloud')]
    counts = cur.fetchall()
    if not counts:
        return

    counts.sort(reverse=1)
    most = counts[0][0]
    thresh = min(int(most * 0.1), thresh)
    nwords = len(counts)
    if len(counts) > limit and counts[limit-1][0] > thresh:
        thresh = counts[limit-1][0]
        nwords = limit
    words = []
    for i, (count, word) in enumerate(counts):
        if count < thresh:
            break
        if i >= limit:
            break
        size = (count - thresh)/(most - thresh)*1.6 + (nwords - i)/float(nwords)*0.6 + 0.5
        words.append((word, size))
    words.sort()
    for word, size in words:
        # out.append(' ') would be necessary if we didn't \n
        out.append(tag_link_elt(word,
                                style=('font-size: %fem; text-decoration: none;'
                                       % (size,))))
    return out
           
def display_random_thumbs(n, since=None, roll_id=None):
    out = [html.div(id='randomthumbs')]
    sql = 'select oe.id, oe.thumb_relpath from original_exports oe'
    args = []
    if since:
        sql += ', photos p where oe.id=p.id and p.time > ?'
        args.append(since)
    if roll_id:
        if not since:
            sql += ', photos p where oe.id=p.id'
        sql += ' and p.roll_id = ?'
        args.append(roll_id)
    sql += ' order by random() limit ?'
    args.append(n)
    cur = cxn.cursor()
    cur.execute(sql, args)
    for photo_id, thumb_relpath in cur.fetchall():
        out.append(thumb_link_elt(photo_id, None, thumb_relpath))
    return out
           
def display_thumbs_for_tag(tag):
    out = [html.div(id='thumbsfortag')]
    sql = ('select oe.id, oe.thumb_relpath from original_exports oe, '
           '       tags t, photo_tags pt'
           '       where t.id=pt.tag_id and oe.id=pt.photo_id'
           '       and t.name=?')
    cur = cxn.cursor()
    cur.execute(sql, (tag,))
    for photo_id, thumb_relpath in cur.fetchall():
        out.append(thumb_link_elt(photo_id, tag, thumb_relpath))
    return out
           
def display_thumbs_for_roll(roll_id):
    out = [html.div(id='thumbsforroll')]
    sql = ('select oe.id, oe.thumb_relpath from original_exports oe, '
           '       photos p'
           '       where oe.id=p.id and p.roll_id = ?')
    cur = cxn.cursor()
    cur.execute(sql, (roll_id,))
    for photo_id, thumb_relpath in cur.fetchall():
        out.append(thumb_link_elt(photo_id, None, thumb_relpath))
    return out
           
def display_tags_for_photo(photo):
    out = [html.div(id='tagsforphoto', style="text-align: center; margin-top:24px;")]
    sql = ('select t.name from tags t, photo_tags pt '
           '       where t.id=pt.tag_id and pt.photo_id=?')
    cur = cxn.cursor()
    cur.execute(sql, (photo,))
    for tag, in cur.fetchall():
        out.append(tag_link_elt(tag))
    return out

def get_photo_data(path):
    i = Image.open(os.path.join(os.path.dirname(__file__),
                                PHOTOS_RELPATH, path))
    ret = {'width': i.size[0], 'height': i.size[1]}
    return ret

def make_navigation_thumb(photo, tag, direction, roll_id):
    prev = direction == 'previous'
    if tag:
        sql = ('select oe.id, oe.thumb_relpath from original_exports oe, '
               '       tags t, photo_tags pt'
               '       where t.id=pt.tag_id and oe.id=pt.photo_id'
               '       and t.name=?')
        args = (tag,)
    else:
        sql = ('select oe.id, oe.thumb_relpath from original_exports oe,'
               '       photos p where oe.id=p.id and p.roll_id=?')
        args = (roll_id,)
    sql += (' and oe.id %s ? order by oe.id %s limit 1'
            % (prev and '<' or '>', prev and 'desc' or 'asc'))
    args += (int(photo),)
    cur = cxn.cursor()
    cur.execute(sql, args)
    res = cur.fetchone()
    head = html.div(klass=(prev and 'prevthumb' or 'nextthumb'))
    if res:
        return [head, thumb_link_elt(res[0], tag and q(tag), res[1],
                                     [html.br],
                                     (prev and 'Previous' or 'Next')
                                     + (tag and ' in '+tag or ''))]
    elif tag:
        return [head, [nested_a_head('tags/' + q(tag)),
                       [html.br], 'Back to ', tag]]
    else:
        return [head, [roll_a_head(roll_id), 'Back to roll']]

def display_exif_info(relpath):
    f = open(os.path.join(os.path.dirname(__file__),
                          PHOTOS_RELPATH, relpath), 'r')
    data = EXIF.process_file(f)
    out = [html.p(klass="exif")]
    for k, v in (('EXIF DateTimeOriginal', 'Time Taken'),
                 ('Image Make', 'Camera Manufacturer'),
                 ('Image Model', 'Camera Model'),
                 ('EXIF FocalLength', 'Real Focal Length'),
                 ('FIXME what here?', 'Focal Length Relative to 35mm Film'),
                 ('EXIF FNumber', 'F Stop'),
                 ('EXIF ExposureTime', 'Time of Exposure'),
                 ('EXIF Flash', 'Flash')):
        if k in data:
            if len(out) > 1:
                out.append(' | ')
            out.append([html.span(title=v), smart_str(data[k])])
    f.close()
    return out

def display_photo(photo, tag):
    sql = ('select normal_relpath, mq_relpath, hq_relpath, roll_id '
           'from original_exports oe, photos p where oe.id=p.id and oe.id=?')
    cur = cxn.cursor()
    cur.execute(sql, (photo,))
    
    try:
        relpath, mq, hq, roll_id = cur.fetchone()
    except TypeError:
        return [html.p, "No such photo:", smart_str(photo)]
    data = get_photo_data(relpath)
    out = [html.div,
           [html.div(id="image", style=("height: %dpx" % data['height'])),
            [html.img(id="preview",
                      width=str(data['width']),
                      height=str(data['height']),
                      src=photourl(relpath))],
            make_navigation_thumb(photo, tag, 'previous', roll_id),
            make_navigation_thumb(photo, tag, 'next', roll_id)],
           display_tags_for_photo(photo),
           display_exif_info(relpath),
           [html.div(id="mqhq"),
            mq and [html.a(href=photourl(mq)), 'MQ'] or '',
            hq and [html.a(href=photourl(hq)), 'HQ'] or '',]]
        
    return [roll_a_head(roll_id), 'roll %d' % roll_id], out

########################################################################
## Pages

def page(body):
    return [html.html,
            [html.head,
             '<!-- This makes IE6 suck less (a bit) -->',
             '<!--[if lt IE 7]>',
             [html.script(src=relurl("inc/styles/ie7/ie7-standard.js"),
                          type="text/javascript")],
             '<![endif]-->',
             [html.title,
              "Photos"],
             [html.link(rel="icon", href=relurl("stock_camera-16.png"),
                        type="image/png")],
             [html.link(rel="shortcut icon", href=relurl("favicon.ico"),
                        type="image/x-icon")],
             [html.link(type="text/css", rel="stylesheet",
                        href=relurl("inc/styles/dark/dark.css"), title="dark",
                        media="screen")],
             [html.link(type="text/css", rel="prefetch alternate stylesheet",
                        href=relurl("inc/styles/classic/classic.css"), title="classic",
                        media="screen")],
             [html.link(type="text/css", rel="prefetch alternate stylesheet",
                        href=relurl("inc/styles/gorilla/gorilla.css"), title="gorilla",
                        media="screen")],
             [html.script(src=relurl("inc/global.js"), type="text/javascript")]],
            [html.body(onLoad="checkForTheme()"),
             [html.div(klass="stylenavbar"),
              [html.div(id="styleshiden", style="display: block;"),
               [html.p,
                [html.a(href="javascript:toggle_div('styleshiden');toggle_div('stylesshown');"),
                 'show styles']]],
              [html.div(id="stylesshown", style="display: none;"),
               [html.ul,
                [html.li,
                 [html.a(href="javascript:setActiveStyleSheet('dark')",
                         title="dark"),
                  'dark']],
                [html.li,
                 [html.a(href="javascript:setActiveStyleSheet('classic')",
                         title="classic"),
                  'classic']],
                [html.li,
                 [html.a(href="javascript:setActiveStyleSheet('gorilla')",
                         title="gorilla"),
                  'gorilla']]],
               [html.p,
                [html.a(href="javascript:toggle_div('styleshiden');toggle_div('stylesshown');"),
                 'hide styles']]]],

             body,

             [html.div(klass="footer"),
              'Copyright &copy; 2006,2007 Andy Wingo',
              [html.br],
              'Powered by a hacked version of ',
              [html.a(href="http://wingolog.org/software/original/"),
               [html.em, 'Original']]]]]

def index():
    return page([html.div(style="text-align: center;"),
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 
                 latest_rolls(3),
                 [rolls_a_head(), "older rolls..."],

                 make_tag_cloud(thresh=1, limit=60),
                 tags_link_elt("more tags..."),
                 display_random_thumbs(6)])

def tags_index():
    return page([html.div,
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 [html.div(klass="navigation"),
                  top_link_elt('Photo Gallery Index'),
                  [html.span, '&gt;', 'Tags']],
                 
                 [html.div(style="text-align: center;"),
                  [html.br],
                  make_tag_cloud(thresh=1, limit=300)]])

def show_tag(tag):
    return page([html.div,
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 [html.div(klass="navigation"),
                  top_link_elt('Photo Gallery Index'),
                  [html.span, '&gt;', tags_link_elt('Tags')],
                  [html.span, '&gt;', tag]],
                 
                 [html.div(style="text-align: center;"),
                  display_thumbs_for_tag(tag),
                  make_tag_cloud(tag)]])

def show_photo(photo, tag):
    roll, content = display_photo(photo, tag)
    return page([html.div,
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 [html.div(klass="navigation"),
                  top_link_elt('Photo Gallery Index'),
                  [html.span, '&gt;', roll],
                  [html.span, '&gt;', 'Photo %d' % photo]],
                 content])

def show_roll(roll_id):
    cur = cxn.cursor()
    sql = 'select time from rolls where id=? limit 1'
    cur.execute(sql, (roll_id,))
    res = cur.fetchall()
    if not res:
        return ''
    else:
        ((t,),) = res
    return page([html.div,
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 [html.div(klass="navigation"),
                  top_link_elt('Photo Gallery Index'),
                  [html.span, '&gt;', [rolls_a_head(), 'Rolls']],
                  [html.span, '&gt;', 'Roll %d'%roll_id]],
                 
                 [html.div(style="text-align: center;"),
                  [html.p,
                   [rolls_a_head(before=t, klass='prevlink'), 'older rolls'],
                   time.strftime(' %d %b %y ', time.gmtime(t)),
                   [rolls_a_head(after=t, klass='nextlink'), 'newer rolls']],

                  display_thumbs_for_roll(roll_id),
                  make_tag_cloud(roll_id=roll_id)]])

def roll_index(before, after, count=7):
    def nav():
        ret = []
        min_time = (after and after + 1) or (res and res[-1][0])
        max_time = (before and before - 1) or (res and res[0][0])
        if min_time:
            ret.append([rolls_a_head(before=min_time), 'older rolls'])
        if max_time:
            ret.append([rolls_a_head(after=max_time), 'newer rolls'])
        if ret:
            return [html.div] + ret
        else:
            return []

    sql = 'select time, id from rolls'
    args = ()
    if before is not None:
        sql += ' where time < ? order by time desc'
        args += (before,)
    elif after is not None:
        sql += ' where time > ? order by time asc'
        args += (after,)
    else:
        sql += ' order by time desc'
    sql += ' limit ?'
    args += (count,)
    cur = cxn.cursor()
    cur.execute(sql, args)
    res = cur.fetchall()
    if before is None and after is not None:
        res.reverse()
    summaries = [roll_summary(roll_id, time) for time, roll_id in res]
    if not summaries:
        summaries = [html.p, 'No rolls found'] 
    return page([html.div(id='rolls'),
                 [html.h1(klass="title"), top_link_elt('Photo Gallery')],
                 [html.div(klass="navigation"),
                  top_link_elt('Photo Gallery Index'),
                  [html.span, '&gt;', 'Rolls']],
                ] + summaries + nav())
    
########################################################################
## mod_python foo

def handler(req):
    global BASE_URI
    global cxn

    thisdir = os.path.dirname(__file__)
    cxn = dbapi2.connect(os.path.join(thisdir, PHOTOS_RELPATH, 'db/photos.db'))

    if req.method != 'GET':
        req.allow_methods(('GET',), True)
        return apache.HTTP_METHOD_NOT_ALLOWED

    uri = req.uri
    path_info = req.path_info
    try:
        args = (req.args and
                dict([x.split('=') for x in (req.args).split('&')]) or {})
        for k, v in args.items():
            args[k] = urllib.unquote_plus(v)
    except ValueError:
        req.write('bad query args: %r' % req.args)
        return apache.OK

    if path_info:
        index_py_uri = uri[:-len(path_info)]
    else:
        index_py_uri = uri
    assert index_py_uri.endswith('index.py')
    BASE_URI = index_py_uri[:-len('index.py')]

    req.content_type = 'text/html'
    req.write('<?xml version="1.0"?>\n')
    req.write('<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" '
              '"http://www.w3.org/TR/2000/REC-xhtml1-20000126/DTD/xhtml1-strict.dtd">\n')
    if path_info:
        if path_info.startswith('/photos/'):
            try:
                photo_id = int(path_info[8:])
            except:
                out = path_info + ' ?? '
            else:
                out = show_photo(photo_id, args.get('tag', None))
        elif path_info.startswith('/tags/'):
            tag = urllib.unquote_plus(path_info[6:])
            if tag:
                out = show_tag(tag)
            else:
                out = tags_index()
        elif path_info.startswith('/rolls/'):
            def tryint(x):
                try:
                    return int(x)
                except:
                    return None
            if path_info == '/rolls/':
                out = roll_index(tryint(args.get('before', None)),
                                 tryint(args.get('after', None)))
            else:
                try:
                    roll_id = int(path_info[7:])
                except:
                    out = path_info + ' ??? '
                else:
                    out = show_roll(roll_id)
        else:
            out = path_info + ' ? '
    else:
        out = index()
    req.write(html2str(out))
    return apache.OK
