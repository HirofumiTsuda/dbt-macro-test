# Drafts of posts

Drafts of the posts for the people who have the problem this tool solves (#79). They are posted by
the maintainer, under their name; nothing here is published by a script.

| File | Where | Language |
|---|---|---|
| `dev-to.md` | [dev.to](https://dev.to/) | English |
| `qiita.md` | [Qiita](https://qiita.com/) | Japanese |

Both are written to be found by what people search ("how to unit test dbt macros", "dbt macro unit
test"), and say no more than the README can back. Everything they show was run: the quick start from
a new environment, the error case, the `ref` case and the `dbt_utils` case (see
[the guide](../../docs/guide.md) and [the sample](../sample_project)). The numbers and the claims
about other tools are those of the README's "Why this exists", which cites its sources.

Before posting: check the version in the install line (`pip install dbt-macro-test`), the address of
the site and the links, and that the output shown is still what `dbt-macro-test run` prints. The
front matter of `dev-to.md` is dev.to's (`published: false` until the maintainer publishes it); the
title and the tags at the top of `qiita.md` are to be pasted into Qiita's form.
