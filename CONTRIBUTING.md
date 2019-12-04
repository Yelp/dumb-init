Contributing to dumb-init
========

`dumb-init` is primarily developed by [Yelp](https://yelp.github.io/), but
contributions are welcome from everyone!

Code is reviewed using GitHub pull requests. To make a contribution, you should:

1. Fork the GitHub repository
2. Push code to a branch on your fork
3. Create a pull request and wait for it to be reviewed

We aim to have all dumb-init behavior covered by tests. If you make a change in
behavior, please add a test to ensure it doesn't regress. We're also happy to
help with suggestions on testing!


## Releasing new versions

`dumb-init` uses [semantic versioning](http://semver.org/). If you're making a
contribution, please don't bump the version number yourself—we'll take care
of that after merging!

The process to release a new version is:

1. Update the version in `VERSION` and run `make VERSION.h`
2. Update the Debian changelog with `dch -v {new version}`.
3. Update the two `wget` urls in the README to point to the new version.
4. Commit the changes and tag the commit like `v1.0.0`.
5. `git push --tags origin master`
6. Wait for Travis to run, then find and download the binary and Debian
   packages for all architectures; there will be links printed at the
   end of the Travis output. Put these into your `dist` directory.
7. Run `make release`
8. Run `twine upload --skip-existing dist/*.tar.gz dist/*.whl` to upload the
   new version to PyPI
9. Upload the resulting Debian packages, binaries, and sha256sums file (all
   inside the `dist` directory) to a new [GitHub
   release](https://github.com/Yelp/dumb-init/releases)
