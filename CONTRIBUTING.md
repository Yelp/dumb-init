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
4. Push these changes as a new branch (has to be on Yelp/dumb-init, not a fork)
   and let Travis build it.
5. Find and download the binary and Debian packages for both amd64 and ppc64el;
   there will be links printed at the end of the Travis output. Put these into
   your `dist` directory.
6. Run `make release`
7. Put your commit on master (no merge or PR needed) and tag the commit like
   `v1.0.0`.
8. `git push --tags origin master`
9. Run `twine upload --skip-existing dist/*.tar.gz dist/*.whl` to upload the
   new version to PyPI
10. Upload the resulting Debian package, binary (inside the `dist` directory),
   and sha256sums file to a new [GitHub
   release](https://github.com/Yelp/dumb-init/releases)
