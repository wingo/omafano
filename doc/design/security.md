# Security

You have photos, and want to organize them, store them on a web server,
and share some of them.  What are the security concerns?  What are the
threats?  How can we design Omafano in such a way that it eliminates or
minimizes the impact of these threats?

## Use cases

Lisa is a young politician.  She takes a lot of photos and would like to
make sure those photos are backed up so that she doesn't lose them.  She
would also like to be able to share photos easily, some with the whole
world but some only to her family and some only with her partner.  It
would be bad for her career if opposition politicians could see her
photos from unguarded moments.

Similarly, Margaret works in sales, and so she travels a lot.  She loves
taking pictures of food and places.  She has a lot of other friends in
sales, including in competitor companies, but this is a danger too --
she needs to control what information she shares with them.  If they
could know where she has been, maybe that would cause her company to
lose a deal.

George is a political activist.  He travels the world, seeing people and
trying to effect social change.  He makes a lot of photos, but wants to
make sure that some collaborators don't appear in any of them, because
that could endanger their personal safety.

## The common threat

What kind of attacker could use photos from Lisa, Margaret, or George
against them?

We should say at the beginning that it is extraordinarily difficult to
stop a determined government attacker.  We can only assume that they can
hack into your phone and your laptop and your server, and at that point
there is no security guarantee that Omafano can provide to you.  George
probably shouldn't use Omafano for photos that would interest the
Mossad, and we explicitly exclude this kind of attacker from our threat
model.

At the same time though, we can impede passive surveillance by
governments, corporations, or fellow users of public wi-fi by applying
standard encryption techniques to data in motion.  More on that below.

The main threat to our users is not from government, however, but rather
from fellow citizens: from Lisa's unhappy constituents, from Margaret's
friends in the sales business, from George's potential employers, and
more generally from the kind of hateful internet user that protagonizes
"movements" like Gamergate and the like.  These peers can be determined
attackers, but usually don't have any privileged position on the
network.  This is the primary threat model for Omafano.

Finally, we should mention one party that we are not considering as a
threat, which is the site operator.  Omafano is web software, and as
much as we would love to have completely distributed web software that
doesn't need servers at all, for Omafano to hit its targets, we are
building it in the "traditional", install-on-a-server way.  We suspect
that one common deployment model will be each installation only has one
user, and in this case security is not degraded in any significant way.
In a situation when someone other than the user runs the server, then
clearly the interests of the operator and the user can diverge.  We'll
be working on our multi-user story as time goes on, and some of our
choices anticipate a multi-user future.  Still, we must assume that the
site operator knows everything.

## Security design

Before getting into the specific measures that Omafano takes to protect
its users, we should re-state the problem that we are trying to solve.
Omafano aims to be usable, simple software that facilitates sharing
_and_ privacy.  It's easy to focus on any one of these four qualities,
but we need to think hard to find an acceptable solution for all parts
of our problem.

With that said, let's go deeper into Omafano's security story.

### Design before code

It starts here.  This security design document is being written before
_any_ of Omafano's code has been started.  We've made web apps before,
and so we know generally what kinds of things can go wrong, and what you
need to get right from the beginning.  We're making software that we
hope will still be running in 10 years, so security can't be an
afterthought.

## Centralized access control

Some web programming environments, notably PHP, promote a design where
entry points to the web application are spread out across the
filesystem.  Omafano is different: it runs as its own web server,
handling all incoming requests in a centralized way, so one can
enumerate the ways that information flows in and out the application and
ensure that your private photos stay private.

## Capabilities-based design

Instead of centering the security analysis on "users" -- who you are --
we focus on "secrets" -- what you know.  Secrets don't grant access to
private information, because they _are_ the private information.  This
kind of design, known as _capabilities_-based design, allows for limpid
analysis of information flow and therefore of who sees what about which
photos.  

One impact of this approach is that Omafano has no users and no
passwords.  User names and passwords are a notorious source of
insecurity, as a breach in one web site allows malicious users to try
out those passwords on other sites, and commonly succeeding.  Instead,
Omafano generates fresh, secure secrets each time you share a photo or a
set of photos, and uses standard browser-based mechanisms to store them
securely.

Technically, this means that Omafano stores its capabilities on the
user's machine in HTTPS-only cookies.  There are other
capabilities-based models that store the secret in the URL itself, but
there are too many ways that the capability can leak in this way:
browser history on shared machines, plaintext leakage if the user types
in a URL without the https://, referrer leaking if the page embeds
third-party resources (Omafano doesn't, FWIW), pre-loading via "rich"
email clients (Facebook used to pre-visit URLS for its own nefarious
purposes), and surely there are more.  With secure cookies, at least the
recipient of a shared secret is unlikely to accidentally leak the
secret.

## Random names

In the same way that shared secrets are random, photo and roll IDs in
Omafano are also random.  Some web services number rolls sequentially,
so that if you know that there is a roll 45, then there are probably
rolls 44 and 46 as well, and your attack surface becomes more
understandable to you.

Still, it's possible in Omafano to give pet names like "Costa Rica
Vacation" to certain rolls or photos, and these pet names can appear in
URLs.  This naturally decreases security -- a pet name is more guessable
than a randomly generated secure secret -- but for photos that you want
to share, perhaps this is less of an issue.

## Memory safety

Many web applications end up using libraries written in C, an unsafe
language that has been an enabling factor in many computer exploits.
Omafano is written in Scheme, a safe language, and so is immune to most
exploits of this kind.

## XSS

Cross-site scripting (XSS) is a vulnerability in which text from the
user is mis-interpreted as code.  Ultimately the responsibility for this
often lies in the web application representing web pages as strings --
it's hard to distinguish one string from another.  Omafano side-steps
this difficulty by building pages from structured data, in which text is
always treated as text and never as code.  This eliminates XSS
vulnerabilities by design.

## CSRF

(I have no good CSRF answer; what do we do?)

## HTTPS only

It's probably an uncontroversial move at this point, but Omafano is
designed to only be available over HTTPS.  Without HTTPS, your photos
are vulnerable to passive snooping.  People sharing wifi with you at the
airport could steal your secrets, and even end up with the ability to
add and delete your photos.  Given that Omafano is a centralized web
application, it is crucial that the connection from the client to the
web application be over HTTPS.

Omafano uses HTTP Strict Transport Security (HSTS) to ensure that typing
"omafano.net" (or your URL) into a browser causes a secure connection to
be made, once you have visited the omafano installation for the first
time.  It also marks its cookies as secure so that they will never leak
into a plain-text HTTP channel.

## Revocable share links

You can easily create "share links" for the photos that you have access
to, which can be pasted into email or any other messaging medium to
share your photos with friends.  Share links are associated with secrets
(capabilities).  Visiting a share link presents the user with a bounce
page that grants them access to that secret -- either permanently, or
only for that browser session.  You can later grant access to more
photos in that same share set.

Like all secrets in Omafano, these shared links and shared secrets have
a record of who created them, and they can be revoked at any time.  Of
course Omafano can't protect against screen captures or saving files to
disk or disk caches or any other thing like that, but this can provide
some useful security to users, especially in the case of device loss.

## Private by default

In Omafano, when you upload photos, they are private by default.  You
have to take action to make them public.  [TODO: flesh out this
workflow]

## Links

https://modelviewculture.com/pieces/social-networking-as-peer-surveillance

http://www.gnu.org/software/guile/manual/html_node/Types-and-the-Web.html
