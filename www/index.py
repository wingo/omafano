from mod_python import apache

import os
import os.path
import time
import urllib
import sqlite
import Image
import EXIF

q = urllib.quote_plus

BASE_URI=None
PHOTOS_RELPATH=''

def relurl(url):
    return BASE_URI + url

def html2str(expr):
    if not isinstance(expr, list):
        return str(expr)
    operator = expr[0]
    args = [html2str(arg) for arg in expr[1:]]
    return str(operator(args))

def _trans(k):
    table = {'klass': 'class'}
    return table.get(k, k)

class html:
    def __getattr__(self, attr):
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

def recent_tags():
    sql = ('select distinct t.name from photo_tags pt, tags t, photos p'
           '       where t.id=pt.tag_id and p.id=pt.photo_id'
           '       and p.time > %d')
    cur = cxn.cursor()
    cur.execute(sql, (int(time.time() - 60 * 60 * 24 * 14),))
    out = [html.p(id='recenttags')]
    words = cur.fetchall()
    if not words:
        return out
    out.append('recent photos in ')
    for word, in words:
        out.append([html.a(href=(relurl('index.py/tags/' + q(word))),
                           style='text-decoration: none'),
                    word])
    return out
           
def make_tag_cloud(*containing_tags):
    sql = ('select t.name, count(pt.photo_id)'
           '       from photo_tags pt, tags t'
           '       where t.id=pt.tag_id')
    if containing_tags:
        sql += (' and pt.photo_id in'
                '     (select distinct pt.photo_id from'
                '      tags t, photo_tags pt'
                '      where t.id=pt.tag_id and (0')
        for tag in containing_tags:
           sql += ' or t.name=%s'
        sql += '))'
        for tag in containing_tags:
           sql += ' and t.name!=%s'
    sql += ' group by t.name order by t.name'
    cur = cxn.cursor()
    cur.execute(sql, containing_tags + containing_tags)
    out = [html.div(id='tagcloud')]
    words = cur.fetchall()
    if not words:
        return out
    most = max([x[1] for x in words])
    thresh = min(int(most * 0.1), 3)
    for word, count in words:
        if count < thresh:
            continue
        # out.append(' ') would be necessary if we didn't \n
        out.append([html.a(href=(relurl('index.py/tags/' + q(word))),
                           style=('font-size: %fem; text-decoration: none;'
                                  % ((count - thresh)/(most - thresh)
                                     * 2.0 + 0.8))),
                    word])
    return out
           
def display_random_thumbs(n, since=None):
    out = [html.div(id='randomthumbs')]
    sql = 'select oe.id, oe.thumb_relpath from original_exports oe'
    args = []
    if since:
        sql += ', photos p where oe.id=p.id and p.time > %d'
        args.append(since)
    sql += ' order by random() limit %d'
    args.append(n)
    cur = cxn.cursor()
    cur.execute(sql, args)
    for photo_id, thumb_relpath in cur.fetchall():
        out.append([html.a(href=(relurl('index.py/photos/%d' % photo_id))),
                    [html.img(src=relurl(PHOTOS_RELPATH + '/' + thumb_relpath))]])
    return out
           
def display_thumbs_for_tag(tag):
    out = [html.div(id='thumbsfortag')]
    sql = ('select oe.id, oe.thumb_relpath from original_exports oe, '
           '       tags t, photo_tags pt'
           '       where t.id=pt.tag_id and oe.id=pt.photo_id'
           '       and t.name=%s')
    cur = cxn.cursor()
    cur.execute(sql, (tag,))
    for photo_id, thumb_relpath in cur.fetchall():
        out.append([html.a(href=(relurl('index.py/photos/%d?tag=%s' %
                                        (photo_id, q(tag))))),
                    [html.img(src=relurl(PHOTOS_RELPATH + '/' + thumb_relpath))]])
    return out
           
def display_tags_for_photo(photo):
    out = [html.div(id='tagsforphoto', style="text-align: center; margin-top:24px;")]
    sql = ('select t.name from tags t, photo_tags pt '
           '       where t.id=pt.tag_id and pt.photo_id=%d')
    cur = cxn.cursor()
    cur.execute(sql, (photo,))
    for tag, in cur.fetchall():
        out.append([html.a(href=(relurl('index.py/tags/%s' % q(tag)))),
                    tag])
    return out

def get_photo_data(path):
    i = Image.open(os.path.join(os.path.dirname(__file__),
                                PHOTOS_RELPATH, path))
    ret = {'width': i.size[0], 'height': i.size[1]}
    return ret

def make_navigation_thumb(photo, tag, direction):
    prev = direction == 'previous'
    if not tag:
        return ''
    sql = ('select oe.id, oe.thumb_relpath from original_exports oe, '
           '       tags t, photo_tags pt'
           '       where t.id=pt.tag_id and oe.id=pt.photo_id'
           '       and t.name=%%s and oe.id %s %%d '
           '       order by oe.id %s limit 1'
           % (prev and '<' or '>', prev and 'desc' or 'asc'))
    cur = cxn.cursor()
    cur.execute(sql, (tag, int(photo)))
    res = cur.fetchone()
    if res:
        return [html.div(klass=(prev and 'prevthumb' or 'nextthumb')),
                [html.a(href=relurl('index.py/photos/%d?tag=%s'
                                    % (res[0], q(tag)))),
                 [html.img(alt="Previous",
                           src=relurl(PHOTOS_RELPATH + '/' + res[1]))],
                 [html.br],
                 prev and 'Previous' or 'Next']]
    else:
        return ''

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
            out.append([html.span(title=v), str(data[k])])
    f.close()
    return out

def display_photo(photo, tag):
    sql = ('select normal_relpath, mq_relpath, hq_relpath '
           'from original_exports where id=%d')
    cur = cxn.cursor()
    cur.execute(sql, (photo,))
    
    try:
        relpath, mq, hq = cur.fetchone()
    except TypeError:
        return [html.p, "No such photo:", str(photo)]
    data = get_photo_data(relpath)
    out = [html.div,
           [html.div(id="image", style=("height: %dpx" % data['height'])),
            [html.img(id="preview",
                      width=str(data['width']),
                      height=str(data['height']),
                      src=relurl(PHOTOS_RELPATH + '/' + relpath))],
            make_navigation_thumb(photo, tag, 'previous'),
            make_navigation_thumb(photo, tag, 'next')],
           display_tags_for_photo(photo),
           display_exif_info(relpath),
           [html.div(id="mqhq"),
            mq and [html.a(href=relurl(PHOTOS_RELPATH + '/' + mq)),
                    'MQ'] or '',
            hq and [html.a(href=relurl(PHOTOS_RELPATH + '/' + hq)),
                    'HQ'] or '',]]
    return out

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
              'Copyright &copy; 2006 Andy Wingo',
              [html.br],
              'Generated by a ',
              [html.a(href="http://wingolog.org/pub/original/"),
               'bastard child'],
              ' of ',
              [html.em,
               [html.a(href="http://jimmac.musichall.cz/original.php3"),
                'Original'],
               'ver. 3.14159']]]]

def index():
    return page([html.div(style="text-align: center;"),
                 [html.h1(klass="title"),
                  [html.a(href=relurl('')),
                   'Photo Gallery']],
                 
                 display_random_thumbs(6),
                 
                 make_tag_cloud(),
                 
                 display_random_thumbs(6, since=(time.time() - 60*60*24*14)),

                 recent_tags()])

def show_tag(tag):
    return page([html.div,
                 [html.h1(klass="title"),
                  [html.a(href=relurl('')),
                   'Photo Gallery:',
                   tag]],
                 [html.div(klass="navigation"),
                  [html.a(href=relurl('')), 'Photo Gallery Index'],
                  '&gt;',
                  [html.a(href=relurl('index.py/tags/'+q(tag))),
                   tag]],
                 
                 [html.div(style="text-align: center;"),
                  display_thumbs_for_tag(tag),
                  make_tag_cloud(tag)]])

def show_photo(photo, tag):
    return page([html.div,
                 [html.h1(klass="title"),
                  [html.a(href=relurl('')),
                   'Photo Gallery']],
                 [html.div(klass="navigation"),
                  [html.a(href=relurl('')), 'Photo Gallery Index'],
                  tag and [html.span,
                           '&gt;',
                           [html.a(href=relurl('index.py/tags/'+q(tag))),
                            tag]] or '',
                  [html.span,
                   '&gt;',
                   "Photo %d" % photo]],
                 
                 display_photo(photo, tag)])

def handler(req):
    global BASE_URI
    global cxn

    thisdir = os.path.dirname(__file__)
    cxn = sqlite.connect(os.path.join(thisdir, PHOTOS_RELPATH, 'db/photos.db'))

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
                out = index()
        else:
            out = path_info + ' ? '
    else:
        out = index()
    req.write(html2str(out))
    return apache.OK
