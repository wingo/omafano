# Site Map

What are the entry points to Omafano?  What are the web pages and what
should they do?

## A note about capabilities

As noted in the security design document, Omafano's permissions model is
based around capabilities.  A capability is a link to information: if
you have the link, you have the information.  Capabilities are stored in
secure cookies by the user's browser.

A user possessing capabilities can share those capabilities with another
user by creating a "share link", which when visited will install those
capabilities on that user's browser.

Each request to Omafano carries the user's capabilities via the `Cookie`
HTTP header.  On the server-side, that set of capabilities is augmented
with the "global" read capability, which is implicitly granted to every
user.  This allows authors to publish their photos for anyone to see.

There are three kinds of capabilities: read caps, share caps, and manage
caps.  You need read caps to read a photo, share caps to create a share,
and manage caps to manipulate rolls and tags, to create photos, or to
delete photos.

## `GET /`

Not yet decided!  Things it could show:

  * Recent photos for the caps that the request has

  * A tag cloud

  * Random photos

  * A featured photo

  * ???

  * A link to a roll index

  * A link to a tag index (as a cloud)

## `GET /photo/PID`

All photo-accessing requests check that the request contains read
capabilities for the given photo.  In practice we check this link in the
reverse direction: if the photo exists, it contains metadata which lists
the capabilities that link to it.  See the database design document.

If the request does not carry read capabilities for the photo, then
Omafano responds with 404 Not Found.  (Responding with 401 Not
Authorized would be another option, but that would leak information
about which photos exist; though, such information is probably already
leaked via differential timing: a not-authorized response, whether 404
or 401, probably takes longer to produce if the photo exists than if it
doesn't.)

### `GET /photo/PID?in-roll=RID`
### `GET /photo/PID?in-tag=NAME`

There are three presentation modes for a photo.  In the bare
`/photo/PID` case, we just show the photo.  However if `in-roll=RID` is
passed, we also show next and previous links for photos in that roll.
Likewise for `in-tag`, for some order of photos.

Note that an in-roll request has to carry read capabilities for the RID,
and that the photo must actually be in the roll.  Likewise, an in-tag
request has to carry read capabilities for the given (NAME, PID) pair.

### `GET /photo/PID/full.jpg`
### `GET /photo/PID/medium.jpg`
### `GET /photo/PID/small.jpg`
### `GET /photo/PID/thumb.jpg`

These get the actual photo at different sizes.  Note that the request
has to go through Omafano in order to ensure that the access checks are
made correctly.

One open question would be that if the web page embeds one of these
images and the user right-clicks and chooses save-as, it would be bad if
the result were named "full.jpg".  Can we serve with a
`Content-Disposition: inline,filename=PID-small.jpg` header and have it
work both for `img src="..."` and for save-as?

## `GET /roll/RID`

Shows the set of photos in a roll.  The request must to carry read
capabilities for the RID.  Rolls are like unique tags with special UI
support for marking a sequential set of photos as being part of a roll.
Rolls usually mark events; "Anne's wedding", etc.

## `GET /rolls`
### `GET /rolls?before=TIMESTAMP`
### `GET /rolls?after=TIMESTAMP`

Shows the 10 most recent rolls which the request can read, optionally
before or after a given timestamp.

## `GET /tag/NAME`

Show linkable thumbnails of all photos that can be read by the request's
capabilities that have the given tag.  Note that tags are associated
with capabilities; a photo might have tags that are unreadable for a
given request.

We probably need to page this response.

## `GET /tags`

Show a cloud of tags that are visible to the request.

## `GET /share/SID`

Inform the user that a photo is being shared in their browser and that
an access token for that photo will be stored in a cookie.  Give them an
option of saving that cookie for this session only or forever.

Show a short message from the person who shared the photo.

Show a form which, when submitted, will POST to /share/SID.

## `POST /share/SID`

Install the corresponding cap into the user's browser, either for the
session or forever.

## `GET /manage`

The /manage tree presents a mirror of the / tree, so
`/manage/photo/PID`, `/manage/rolls`, etc.  The photos, rolls etc to
which you get access are those for which you have manage caps.  For each
of these URLs we will specify the additional views and operations that
can be taken.

## `GET /manage/photo/PID`
## `POST /manage/photo/PID`

Allow changing a photo's tags, or deleting a photo.

## `GET /manage/rolls`

Allow merging of rolls.  Within one cap -- a (manage,share,read) triple
-- a photo only has one roll.

## `GET /manage/roll/RID`
## `POST /manage/roll/RID`

Allow splitting and merging of rolls.  Within one cap -- a
(manage,share,read) tuple -- a photo only has one roll.

## `GET /manage/share`

Show links to all shares that this cap has created, along with private
names for those shares, and the public message that the user will see
for that share.

## `GET /manage/share/SID`

See how many times this share has been installed, and when the last time
was.

## `POST /manage/share/SID`

Revoke a share.

## `POST /create/photo`
## `POST /create/roll`

Create a new photo or roll.  Requires manage caps.
