# Contributing
There are many ways to contribute, including testing, reporting and commenting
on issues, writing documentation, fixing bugs, adding new features, etc. Thank
you for helping make Thicket better.

To get started, spend some time getting to know the project and how we
collaborate as a community of users and developers by reviewing the project
documentation,
[issues](https://github.com/Thicket-Blender/thicket/issues?q=is%3Aissue), and
[PRs](https://github.com/Thicket-Blender/thicket/pulls?q=is%3Apr) (open and
closed).

Be sure to review the [code of conduct](CODE_OF_CONDUCT.md) and help maintain an
open and welcoming environment.

## Goals
Be sure to consider the following project goals when preparing your
contributions. If you are interesting in contributing something with might be
contradictory or significantly out of scope, open an issue and get some feedback
from user, reviewers, and the project maintainers before getting too far in to
implementation.

Thicket aims to (in priority order):
* Follow Blender UI and coding guidelines
* Prioritize Blender built-in features (e.g. Cycles and Eevee)
* Support all platforms supported by Blender and Laubwerk Plant Kits
* Match features and user experience of Laubwerk Plants Add-ons for other applications
* Support commonly used 3rd party render engines

## Coding Style
Thicket follows [PEP8](https://www.python.org/dev/peps/pep-0008/) with 120
character line length and [Blender
Add-on](https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html)
guidelines. Before commiting your code, even locally, be sure to run the
`test/pep8.sh` script which will scan your code and report on both critical
(must fix) and informational warnings (may need fixing).

## Testing
Blender runs on multiple platforms. Thicket supports all platforms that Laubwerk
ships Plant Kits for (currently Mac and Windows). Blender also supports multiple
Render Engines. This creates a complex set of heterogeneous environments
supported by Thicket.

At a minimum, test your changes on the current version of Blender, the oldest
supported version of Blender, and using the built-in Eevee and Cycles renderers.
Whenever possible, test on as many operating systems and render engines as
possible. Be prepared for users, reviewers, and/or maintainers to request
changes to ensure changes do not break or otherwise impair environments other
than the one you targeted.

## Preparing Commits
Software is not made of files, functions, and variables. Software is made of
change. Without the change history, software is a static snapshot in time. When
preparing your changes and your commit messages, consider them equally valuable
as the content itself.

Organize your changes into independent topical commits. Each commit should be
self-sufficient and address one issue. Be sure to document each change with a
short subject line followed by a blank line and longer description of why the
change is needed, how the issue manifests, and what is being changed. This makes
it easier to review your changes, find bugs in the future, and manage releases.

Chris Beams's [How to Write a Git Commit
Message](https://chris.beams.io/posts/git-commit) offers a good introduction
into the why and how of revision control best practices.

If you are addressing an open issue, include a `Fixes:` tag. This helps keep
everyone involved up to date by connecting the commit with the Issue.

`Fixes: Issue #99: Issue description`

Finally, sign off your commit messages. You can automatically add your
`Signed-off-by:` tag with `git commit -s`. See https://developercertificate.org
for a definition of the Developer Certificate of Origin.

`Signed-off-by: Your Name \<email address\>`

For example:

```
Refactor material generation pipeline

Laubwerk materials contain properties per side and properties for the
material overall. Update the material creation to be a multistage
pipeline with several optional stages (such as two-sided, alpha,
subsurface, etc.).

Refactor the Laubwerk material side specifc property handling into a
separate lbw_side_to_bsdf() function, simplifying the handling of the
two-sided materials.

Now that each side is represented as its own Principled BSDF shader, the
alpha needs to be handled later in the pipeline. Introduce a new
transparency stage to handle alpha.

Take note of the Laubwerk side properties Thicket currently ignores.

Fixes: Issue #32: Two sided materials should use Mix Shader instead of regular mix node

Signed-off-by: Darren Hart <dvhart@infradead.org>

```

## Pull Requests
To submit a contribution, follow the traditional GitHub workflow:
https://guides.github.com/activities/forking/

Be prepared to receive feedback and follow-up with requested changes. Your
changes will be reviewed to ensure they address all use cases, work on all
platforms, and are generally inline with the goals and intents of the project.
