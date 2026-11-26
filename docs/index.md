# dbt-macro-test

**Test your dbt macros.**

Call a macro with the arguments you choose, say what it should return, and run it on your machine
or in CI. A test is a few lines of YAML; the tool turns each case into one of dbt's own unit tests,
so the result, and the diff when it fails, are dbt's.

![dbt-macro-test run on the sample project: the 26 cases are listed and pass; after one expected value is changed, that case fails and dbt's diff is shown](images/demo.gif)

## Quick start

--8<-- "README.md:quickstart"

## Where to go next

- **[Guide](guide.md)**: what to write for the macro you have (a value, columns, text, an error, a
  `ref`, a macro that writes), with an example for each. Every example runs in CI.
- **[Spec reference](spec.md)**: every key of a spec.
- **[Design](design.md)**: how it works, and why it is built this way.
- **[Changelog](changelog.md)**.
- [The README](https://github.com/HirofumiTsuda/dbt-macro-test#readme) says why this exists, what
  is carried over from your project, how to use it in CI, and what is not supported.
