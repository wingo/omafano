# Internationalization

How will Omafano support multiple languages?

## Global site language

In the simple case where an Omafano installation has only one user, the
user should be able to set the interface language as a global
preference.  We will use gettext to internationalize the text on the
site.

## Language that visitors see

The site will have a default language.  Individual visitors can choose
other languages via links on the page.  This will redirect them to
alternate URLs, like instead of

  omafano.net/photo/1234

the user will be redirected to

  omafano.net/+es-mx/photo/1234

All internal links from an +es-mx page will link to +es-mx.  To change
language, the user can click on a language list in the footer.  Here,
"es-mx" is a RFC 5646 language tag.  If that specific language tag isn't
supported yet in Omafano, the user will be redirected to a more general
tag, or otherwise given a generic error message and a link to the
corresponding generic page.

It might be useful at some point to store the user's preferred language
in a cookie, but that can be tricky.

## Links

RFC 5646: https://tools.ietf.org/html/rfc5646

RFG 4647: https://tools.ietf.org/html/rfc4647
