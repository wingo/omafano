# Scaling

Is Omafano appropriate for a single-user installation?  What about a
commercial instance with thousands of users?  This document describes
the spectrum of Omafano use cases, with limitations and possible
solutions.

## Database

### Thousands of photos

In the beginning we are targetting single-user deployments.  We use Git
as a graph-based database; the "master" branch stores the whole of the
data, and there is an "index" branch that contains indexing data, and is
recomputed when master changes.  Git is simple and scales to gigabytes
of data.  That's not very far, of course, but it's enough for the
initial needs of just a few users per installation.

One photo might have 4 KB per photo, so 1000 photos would occupy 4 MB of
metadata per user, and at maybe 5 MB per photo, that would be 5 GB of
data.  That's big for a Git repository but it's not a large number of
objects, so you could store the photos and the metadata together in one
repository for simplicity.

### Hundreds of thousands of photos

For the single-user case, photos are stored in Git as normal Git
objects.  The obvious next step is to store them in some other data
store, though sharding is not yet necessary if there are SSDs.  1M
photos at 5MB per photo is 5 terabytes of memory, which reasonable for a
single server.  Other metadata can remain in Git, and in practice
remains in memory due to indexing.

If there are 1M photos, and each photo has 4 KB of metadata, then
that's 4 GB of metadata, which is pushing the limits of Guile's GC,
though, so this is really the limit for in-memory metadata.  We would
have to index in different ways.

### Hundreds of millions of photos

It will probably never get here :)  However, you could store the photos
in S3, and the metadata for 1B photos would still fit in a machine with
1TB of memory; and given that photos have random identifiers, they shard
transparently as well.  But I won't speculate any more here.

One challenge you will have here is reindexing the database as things
change.  Omafano uses a functional interface to the database, whereby
you can get a reference to the state of the database at any time,
perform diffs between states, etc.  This is the Git model, and is also
the model taken by the Datomic database.  However careful thought would
be needed at the billion-photo level to allow the update throughput that
you want.

## Compute

### 1000 real requests per second

This is about the design limit for a single Omafano process.  Also,
Omafano's responses are designed to be easily cacheable, so the backend
shouldn't need to handle too many strange requests.  This corresponds
probably to a hundred active users or so.

### 100,000 real requests per second

This is a really high request rate and we shouldn't really plan for it.
That said, given the functional approach to the database, we can use
multiple cores of a machine, which should provide an N-fold boost.  More
than that, we have to start looking at external databases like Datomic +
S3 or something.

## Bandwidth

### Single-user case

One nginx proxy sits in front of the Omafano process.  The proxy handles
SSL termination.  Omafano serves photos directly.

### Multi-user case

One nginx proxy sits in front of the Omafano process.  The proxy handles
SSL termination.  Omafano bounces photo responses off nginx using
X-accel, and some other process or processes actually serve the photos.
There can be multiple nginx proxies and multiple image-serving processes
but there is still one main Omafano process.

We could scale more but this is enough of a sketch.
