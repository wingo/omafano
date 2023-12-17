;; Omafano
;; Copyright (C) 2014 Andy Wingo <wingo at pobox dot com>

;; This program is free software; you can redistribute it and/or modify
;; it under the terms of the GNU General Public License as published by
;; the Free Software Foundation; either version 3 of the License, or (at
;; your option) any later version.
;;
;; This program is distributed in the hope that it will be useful,
;; but WITHOUT ANY WARRANTY; without even the implied warranty of
;; MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
;; General Public License for more details.
;;
;; You should have received a copy of the GNU General Public License
;; along with this program; if not, see <http://www.gnu.org/licenses/>.

(define-module (omafano)
  #:use-module (ice-9 match)
  #:use-module (ice-9 format)
  #:use-module (sqlite3)
  #:use-module (jpeg)
  #:use-module (srfi srfi-1)
  #:use-module (srfi srfi-19)
  #:use-module (sxml simple)
  #:use-module (web request)
  #:use-module (web response)
  #:use-module (web server)
  #:use-module (web uri)
  #:declarative? #f
  #:export (main))

(define *public-host* "127.0.0.1")
(define *public-port* 8081)
(define *public-path-base* '("photos"))

(define *private-host* "127.0.0.1")
(define *private-port* 8081)
(define *private-path-base* '("photos"))

(define *server-impl* 'http)
(define *server-impl-args*
  (lambda () `(#:host ,*private-host* #:port ,*private-port*)))

(define *db* (sqlite-open "db/photos.db" SQLITE_OPEN_READONLY))

(define html5-doctype "<!DOCTYPE html>\n")
(define *title* "Photos")
(define *subtitle* "")

(define *author-name* "Alice Hacker")
(define *author-url* "http://example.com/")
(define *copyright-years* "1999")

(define (timestamp->date timestamp)
  (time-utc->date (make-time time-utc 0 timestamp) 0))
(define (timestamp->atom-date timestamp)
  (date->string (timestamp->date timestamp) "~Y-~m-~dT~H:~M:~SZ"))

(define (list-join l infix)
  (match l
    (() '())
    ((_) l)
    ((a . l) (cons* a infix (list-join l infix)))))

(define* (parse-www-form-urlencoded str #:optional (charset "utf-8"))
  (map
   (lambda (piece)
     (let ((equals (string-index piece #\=)))
       (if equals
           (cons (uri-decode (substring piece 0 equals) #:encoding charset)
                 (uri-decode (substring piece (1+ equals)) #:encoding charset))
           (cons (uri-decode piece #:encoding charset) ""))))
   (string-split str #\&)))
(define (uri-query-params uri)
  (match (uri-query uri)
    (#f '())
    (params (parse-www-form-urlencoded params))))

(define (make-sxml-navigation navigation)
  (let lp ((nav navigation) (path '()))
    (match nav
      (() '())
      ((tok . nav)
       (let ((tok (if (string? tok) tok (object->string tok))))
         (cons* " → "
                (link (append-reverse path (list tok)) (list tok))
                (lp nav (cons tok path))))))))

(define* (templatize #:key (title *title*) (body '((p "No body")))
                     (navigation '()))
  `(html (head (title ,title)
               (meta (@ (name "viewport") (content "width=device-width")))
               (link (@ (rel "stylesheet")
                        (href ,(relpath '("omafano.css")))
                        (type "text/css"))))
         (body (div (@ (id "navigation"))
                    (h1 (@ (id "title")) ,(link '() (list title)))
                    ,@navigation)
               (div (@ (id "content")) ,@body)
               (div (@ (id "colophon"))
                         "Copyright " ,*copyright-years* " " ,*author-name*
                         ".  Powered by "
                         (a (@ (href "http://wingolog.org/software/omafano/"))
                            (em "Omafano"))
                         "."))))

(define* (respond #:optional body #:key
                  (status 200)
                  (title *title*)
                  (doctype html5-doctype)
                  (content-type-params '((charset . "utf-8")))
                  (content-type 'text/html)
                  (navigation '())
                  (sxml-navigation (make-sxml-navigation navigation))
                  (extra-headers '())
                  (sxml (and body (templatize #:title title #:body body
                                              #:navigation sxml-navigation))))
  (values (build-response
           #:code status
           #:headers `((content-type . (,content-type ,@content-type-params))
                       ,@extra-headers))
          (lambda (port)
            (if sxml
                (begin
                  (if doctype (display doctype port))
                  (sxml->xml sxml port))))))

;; (put 'match-values 'scheme-indent-function 1)
(define-syntax-rule (match-values producer consumer ...)
  (call-with-values (lambda () producer)
    (match-lambda* consumer ...)))

(define (split-path path)
  "Split a file system path into components to be encoded into a URI path."
  (string-split path #\/))

(define (encode-query-params params)
  (define (->string s) (if (string? s) s (object->string s)))
  (define (encode-query-param param)
    (match param
      ((k . v)
       (string-append (uri-encode (->string k))
                      "="
                      (uri-encode (->string v))))))
  (string-join (map encode-query-param params) "&"))

(define* (relpath path #:optional (params '()))
  (let ((path-str (encode-and-join-uri-path (append *public-path-base* path))))
    (if (null? params)
        (string-append "/" path-str)
        (string-append "/" path-str "?" (encode-query-params params)))))

(define* (relurl path #:optional (params '()))
  (uri->string (build-uri 'http
                          #:host *public-host*
                          #:port *public-port*
                          #:path (relpath path)
                          #:query (and (pair? params)
                                       (encode-query-params params)))))

(define* (link path body #:key (attrs '()) (params '()))
  `(a (@ (href ,(relpath path params)) . ,attrs)
      . ,body))
(define* (photo-link id body #:key (attrs '()) tag)
  (link `("photos" ,(number->string id)) body
        #:attrs attrs #:params (if tag `((tag . ,tag)) '())))
(define* (roll-link id body #:key (attrs '()))
  (link `("rolls" ,(number->string id)) body #:attrs attrs))
(define* (rolls-link body #:key before after (attrs '()))
  (link `("rolls") body #:attrs attrs
        #:params `(,@(if before `((before . ,before)) '())
                   ,@(if after `((after . ,after)) '()))))
(define* (tag-link tag #:key (attrs '()))
  (link `("tags" ,tag) (list tag) #:attrs attrs))
(define* (tags-link body #:key (attrs '()))
  (link `("tags") body #:attrs attrs))
(define* (thumb-link id tag path . body)
  (photo-link id `((div (@ (class "thumb"))
                         (img (@ (src ,(relpath (split-path path))))))
                   . ,body)
              #:tag tag))

(define *stmt-cache* (make-hash-table))
(define (sqlite-prepare/cached *db* sql)
  (cond
   ((hash-ref *stmt-cache* sql)
    => (lambda (stmt)
         (sqlite-reset stmt)
         stmt))
   (else
    (let ((stmt (sqlite-prepare *db* sql)))
      (hash-set! *stmt-cache* sql stmt)
      stmt))))

(define* (make-query #:optional (sql "") . args)
  (vector sql (reverse args)))
(define (query+ query sql* args*)
  (match query
    (#(sql args)
     (vector (string-append sql sql*) (append-reverse args* args)))))
(define (run-query query)
  (match query
    (#(sql reversed-args)
     (let ((stmt (sqlite-prepare/cached *db* sql)))
       (fold (lambda (arg idx)
               (sqlite-bind stmt idx arg)
               (1+ idx))
             1
             (reverse reversed-args))
       stmt))))
(define (query-fold cons nil query)
  (sqlite-fold cons nil (run-query query)))
(define (query-fold-right cons nil query)
  (sqlite-fold-right cons nil (run-query query)))
(define (query-map f query)
  (query-fold-right (lambda (a tail) (cons (f a) tail)) '() query))
(define (query-results query)
  (query-fold-right cons '() query))

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Parts of pages

(define* (roll-summary roll-id roll-time #:key (random? #t))
  `(p (@ (class "roll"))
      ,(if random?
           (random-thumbs 5 #:roll-id roll-id)
           (thumbs-for-roll roll-id))
      ,@(if roll-time
            `((br)
              ,(roll-link
                roll-id
                (list (strftime "%d %b %y" (gmtime roll-time)))
                #:attrs '((class . "roll-title")
                          (style . "text-decoration: none; font-weight: bold")))
              (br))
            '())
      ,@(list-join
         (query-map
          (match-lambda
           (#(tag)
            (tag-link tag #:attrs '((style . "text-decoration: none")))))
          (make-query
           "select distinct t.name
             from photo_tags pt, tags t, photos p
             where t.id=pt.tag_id and p.id=pt.photo_id and p.roll_id = ?"
           roll-id))
         " ")))

(define* (latest-rolls #:optional (limit 1))
  `(div (@ (class "latest-rolls"))
        ,@(query-map
           (match-lambda
            (#(roll-id roll-time) (roll-summary roll-id roll-time)))
           (make-query
            "select id, time from rolls order by time desc limit ?"
            limit))))
           
(define* (tag-cloud #:key tag (limit 100) (thresh 1) roll-id)
  (define (apply-threshold results thresh)
    (if (<= thresh 1)
        results
        (filter (match-lambda (#(count _) (<= thresh count))) results)))
  (let ((q (make-query)))
    (define (q+! str . args) (set! q (query+ q str args)))
    (q+! "select count(pt.photo_id), t.name")
    (q+! " from photo_tags pt, tags t")
    (when roll-id (q+! ", photos p"))
    (q+! " where t.id=pt.tag_id")
    (when roll-id (q+! " and pt.photo_id=p.id and p.roll_id=?" roll-id))
    (when tag
      (q+! " and pt.photo_id in")
      (q+! "  (select distinct pt.photo_id from tags t, photo_tags pt")
      (q+! "    where t.id=pt.tag_id and t.name=?)" tag)
      (q+! " and t.name!=?" tag))
    (q+! " group by t.name order by count(pt.photo_id) desc")
    (when limit
      (q+! " limit ?" limit))
    (let* ((results (query-results q)))
      (match results
        (() '(div (@ (class "tagcloud"))))
        ((#(max-count _) . _)
         (let ((thresh (min (* max-count 0.1) thresh)))
           `(div
             (@ (class "tagcloud"))
             ,@(list-join
                (map
                 (match-lambda
                  (#(count tag)
                   (let* ((size (+ 0.5
                                   (* (/ (- count thresh) (- max-count thresh))
                                      1.6)))
                          (style
                           (format #f "font-size:~,2fem; text-decoration:none"
                                   size)))
                     (tag-link tag #:attrs `((style . ,style))))))
                 (sort
                  (apply-threshold results thresh)
                  (match-lambda* ((#(_ a) #(_ b)) (string<=? a b)))))
                " "))))))))
           
(define* (random-thumbs n #:key since roll-id)
  (let ((q (make-query)))
    (define (q+! str . args) (set! q (query+ q str args)))
    (q+! "select oe.id, oe.thumb_relpath from original_exports oe")
    (when since
      (q+! ", photos p where oe.id=p.id and p.time > ?" since))
    (when roll-id
      (unless since (q+! ", photos p where oe.id=p.id"))
      (q+! " and p.roll_id=?" roll-id))
    (q+! " order by random() limit ?" n)
    `(div (@ (class "randomthumbs"))
          ,@(query-map
             (match-lambda
              (#(id thumb-relpath) (thumb-link id #f thumb-relpath)))
             q))))
           
(define (thumbs-for-tag tag)
  `(div (@ (class "thumbsfortag"))
        ,@(query-map
           (match-lambda
            (#(id thumb-relpath) (thumb-link id tag thumb-relpath)))
           (make-query
            "select oe.id, oe.thumb_relpath from original_exports oe,
                          tags t, photo_tags pt
                          where t.id=pt.tag_id and oe.id=pt.photo_id and t.name=?"
            tag))))
           
(define (thumbs-for-roll roll-id)
  `(div (@ (class "thumbsforroll"))
        ,@(query-map
           (match-lambda
            (#(id thumb-relpath) (thumb-link id #f thumb-relpath)))
           (make-query "select oe.id, oe.thumb_relpath from original_exports oe,
                          photos p where oe.id=p.id and p.roll_id=?"
                       roll-id))))
           
(define (tags-for-photo photo)
  `(div (@ (class "tagsforphoto"))
        ,@(list-join
           (query-map
            (match-lambda (#(tag) (tag-link tag)))
            (make-query "select t.name from tags t, photo_tags pt
                         where t.id=pt.tag_id and pt.photo_id=?"
                        photo))
           " ")))
           
(define (photo-metadata path)
  (catch #t
    (lambda () (jpeg-dimensions-and-exif path))
    (lambda (k . args)
      (print-exception (current-output-port) #f k args)
      (values #f #f '()))))

(define* (navigation-thumb photo tag direction roll-id)
  (let ((q (make-query)))
    (define (q+! str . args) (set! q (query+ q str args)))
    (if tag
        (q+! "select oe.id, oe.thumb_relpath from original_exports oe,
                 tags t, photo_tags pt
                 where t.id=pt.tag_id and oe.id=pt.photo_id
                 and t.name=?" tag)
        (q+! "select oe.id, oe.thumb_relpath from original_exports oe, photos p
                 where oe.id=p.id and p.roll_id=?" roll-id))
    (match direction
      ('previous (q+! " and oe.id<? order by oe.id desc limit 1" photo))
      ('next     (q+! " and oe.id>? order by oe.id asc limit 1" photo)))
    `(div (@ (class ,(match direction
                       ('previous "prevthumb") ('next "nextthumb"))))
          ,(match (query-results q)
             (()
              (if tag
                  (link (list "tags" tag) `("Back to " ,tag))
                  (link (list "rolls" (number->string roll-id))
                        '("Back to roll"))))
             ((#(id thumb-relpath))
              (thumb-link id tag thumb-relpath
                          '(br)
                          (match direction
                            ('previous "Previous") ('next "Next"))
                          (if tag (string-append " in " tag) "")))))))

(define (format-value value)
  (cond ((string? value) value)
        ((number? value) value)
        ((pair? value) (/ (car value) (cdr value)))
        (else (error "don't know how to format" value))))
(define (format-float value)
  (format #f "~,2f" (/ (car value) (cdr value))))

(define-syntax-rule (define-exif-tags table
                      (sym-name str-name formatter)
                      ...)
  (begin
    (define table (make-hash-table))
    (hashq-set! table 'sym-name (cons str-name formatter))
    ...))

(define-exif-tags *exif-tags*
  (date-time-original "Time Taken" format-value)
  (make "Camera Manufacturer" format-value)
  (model "Camera Model" format-value)
  (focal-length "Focal Length" format-float)
  (f-number "F Stop" format-float)
  (exposure-time "Exposure Time" format-value)
  (flash "Flash" (lambda (alist)
                   (and (assq-ref alist 'fired?) "Flash fired"))))

(define (display-photo photo tag)
  (match (query-results
          (make-query "select normal_relpath, mq_relpath, hq_relpath, roll_id
                        from original_exports oe, photos p
                        where oe.id=p.id and oe.id=?"
                      photo))
    (() (values #f `(p "No such photo: " ,photo)))
    ((#(path mq hq roll-id))
     (match-values (photo-metadata path)
       ((width height exif)
        (values
         roll-id
         `(div
           (div (@ (id "image"))
                ,(navigation-thumb photo tag 'previous roll-id)
                ,(navigation-thumb photo tag 'next roll-id)
                (img (@ (id "preview") (alt "")
                        (src ,(relpath (split-path path)))
                        ,@(if (and width height)
                              `((width ,width) (height ,height))
                              '()))))
           ,(tags-for-photo photo)
           (p (@ (class "exif"))
              ,@(list-join
                 (filter-map
                  (match-lambda
                   ((name . value)
                    (match (hashq-ref *exif-tags* name)
                      (#f #f)
                      ((name . formatter)
                       (let ((formatted (formatter value)))
                         (and formatted
                              `(span (@ (title ,name)) ,formatted)))))))
                  exif)
                 " | "))
           ,@(let ((mq (and mq (link (split-path mq) '("medium-res"))))
                   (hq (and hq (link (split-path hq) '("high-res")))))
               (if (or mq hq)
                   `((div (@ (id "mqhq"))
                          "(" ,@(if mq
                                    (cons* mq (if hq (list ", " hq) '()))
                                    (list hq))
                          ")"))
                   '())))))))))

;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;
;; Pages

(define (index)
  (respond `(,(latest-rolls 1)
             ,(tag-cloud #:limit 60)
             (p ,(rolls-link '("browse by roll"))
                " "
                ,(tags-link '("browse by tag")))
             ,(random-thumbs 5))))

(define (show-photo photo tag)
  (match-values (display-photo photo tag)
    ((#f content)
     (respond (list content) #:status 404))
    ((roll content)
     (respond `(,content)
              #:sxml-navigation
              `(" → "
                ,(roll-link roll
                            (list (format #f "roll ~a" roll)))
                " → "
                ,(link `("photos" ,(number->string photo))
                       (list (number->string photo))))))))

(define (tags-index)
  (respond `((div (@ (style "text-align: center"))
                  (br)
                  ,(tag-cloud #:limit 300)))
           #:navigation '("tags")))

(define (show-tag tag)
  (respond `((div (@ (style "text-align: center"))
                  ,(thumbs-for-tag tag)
                  ,(tag-cloud #:tag tag)))
           #:navigation `("tags" ,tag)))

(define* (rolls-index before after #:key (count 7))
  (let ((q (make-query)))
    (define (q+! str . args) (set! q (query+ q str args)))
    (q+! "select time, id from rolls")
    (cond
     (before (q+! " where time < ? order by time desc" before))
     (after (q+! " where time > ? order by time asc" after))
     (else (q+! " order by time desc")))
    (q+! " limit ?" count)
    (let* ((results (query-results q))
           (results (if (and (not before) after) (reverse results) results))
           (summaries (map (match-lambda
                            (#(time roll-id) (roll-summary roll-id time)))
                           results)))
      (respond
       `((div (@ (id "rolls"))
              ,@(if (null? summaries)
                    `((p "No rolls found"))
                    (let ((min-time (or (and=> after 1+)
                                        (match results
                                          ((_ ... #(time _)) (1- time)))))
                          (max-time (or (and=> before 1-)
                                        (match results
                                          ((#(time _) . _) (1+ time))))))
                      `(,@summaries
                        ,(if min-time
                             (rolls-link '("older rolls") #:before min-time)
                             '(span))
                        " "
                        ,(if max-time
                             (rolls-link '("newer rolls") #:after max-time)
                             '(span)))))))
       #:navigation '("rolls")))))
    
(define (show-roll roll-id)
  (match (query-results
          (make-query "select time from rolls where id=? limit 1"
                      roll-id))
    (() (respond `((p "No roll found: " ,roll-id)) #:status 404))
    ((#(time))
     (respond
      `((div (@ (style "text-align: center"))
             (p ,(rolls-link '("older rolls") #:before time
                             #:attrs '((class . "prevlink")))
                ,(strftime " %d %b %y " (gmtime time))
                ,(rolls-link '("newer rolls") #:after time
                             #:attrs '((class . "prevlink")))))
        ,(thumbs-for-roll roll-id)
        ,(tag-cloud #:roll-id roll-id))
      #:navigation `("rolls" ,roll-id)))))

(define* (rolls-atom #:key (num-rolls 5))
  (let* ((rolls (query-results
                 (make-query
                  "select id, time from rolls order by time desc limit ?"
                  num-rolls)))
         (updated (match rolls
                    ((#(roll-id roll-time) . _) roll-time)
                    (_ #f))))
    (respond
     #f
     #:extra-headers (if updated
                         `((last-modified . ,(timestamp->date updated)))
                         '())
     #:doctype #f
     #:content-type 'application/atom+xml
     #:sxml
     `(feed
       (@ (xmlns "http://www.w3.org/2005/Atom")
          ;; FIXME: is this right?
          (xml:base ,(relurl '())))
       (title (@ (type "text")) ,*title*)
       (subtitle (@ (type "text")) ,*subtitle*)
       ,@(if updated
             `((updated ,(timestamp->atom-date updated)))
             '())
       (generator (@ (uri "http://wingolog.org/software/omafano")
                     (version "3.141592"))
                  "Omafano")
       (link (@ (rel "alternate") (type "text/html")
                (href ,(relurl '()))))
       (id ,(relurl '("rolls" "atom")))
       (link (@ (rel "self") (type "application/atom+xml")
                (href ,(relurl '("rolls" "atom")))))
       ,@(map (match-lambda
               (#(roll-id roll-time)
                (let ((roll-url (relurl `("rolls" ,(number->string roll-id)))))
                  `(entry (author (name ,*author-name*) (uri ,*author-url*))
                          (title (@ (type "text"))
                                 ,(strftime "%d %b %y" (gmtime roll-time)))
                          (link (@ (rel "alternate") (type "text/html")
                                   (href ,roll-url)))
                          (id ,roll-url)
                          (updated ,(timestamp->atom-date roll-time))
                          (published ,(timestamp->atom-date roll-time))
                          (content
                           (@ (type "xhtml"))
                           (div (@ (xmlns "http://www.w3.org/1999/xhtml"))
                                ,(roll-summary roll-id roll-time
                                               #:random? #f)))))))
              rolls)))))

   (define (handle request body)
     (let ((uri (request-uri request))
           (method (request-method request)))
       (define (id? str)
         (and=> (string->number str)
                (lambda (n) (and (exact-integer? n) (not (negative? n))))))
       (define (remove-base path base)
         (match base
           (() path)
           ((head . base)
            (match path
              ((head* . path)
               (and (equal? head head*) (remove-base path base)))
              (_ #f)))))
       (case method
         ((GET HEAD)
          (match (remove-base (split-and-decode-uri-path (uri-path uri))
                              *private-path-base*)
            (()
             (index))
            (("photos" (? id? photo))
             (show-photo (string->number photo)
                         (assoc-ref (uri-query-params uri) "tag")))
            (("tags")
             (tags-index))
            (("tags" tag)
             (show-tag tag))
            (("rolls")
             (let* ((params (uri-query-params uri))
                    (before (assoc-ref params "before"))
                    (after (assoc-ref params "after")))
               (rolls-index (and before (id? before) (string->number before))
                            (and after (id? after) (string->number after)))))
            (("rolls" (? id? roll))
             (show-roll (string->number roll)))
            (("rolls" "atom")
             (rolls-atom))
            (_
             (respond `((h1 "Page not found")
                        (p "Unknown path: " ,(uri-path uri)))
                      #:status 404))))
         (else (respond #:status 405)))))

;; The seemingly useless lambda is to allow for `handle' to be
;; redefined at runtime.
(define (main-loop)
  (run-server (lambda (r b) (handle r b))
              *server-impl*
              (if (list? *server-impl-args*)
                  *server-impl-args*
                  (*server-impl-args*))))

(define (main . args)
  (main-loop))
