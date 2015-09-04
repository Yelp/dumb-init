Contributing to dumb-init
========

`dumb-init` is primarily developed by [Yelp](https://yelp.github.io/), but
contributions are welcome from everyone!

Code is reviewed using GitHub pull requests. To make a contribution, you should:

1. Fork the GitHub repository
2. Push code to a branch on your fork
3. Create a pull request and wait for it to be reviewed


## Releasing new versions

`dumb-init` uses [semantic versioning](http://semver.org/). If you're making a
contribution, please don't bump the version number yourself—we'll take care
of that after merging!

The process to release a new version is:

1. Run integration tests (`make itest`). Travis doesn't run these, so it's a
   good idea to make sure they still pass.
2. Update the version in `setup.py`
3. Update the Debian changelog with `dch -v {new version}`.
4. Commit the changes and tag the commit like `v1.0.0`.
5. `git push --tags origin master`
6. Run `rm -rf dist && python setup.py sdist` to create a source distribution
7. Run `twine dist/*` to upload the new version to PyPI
8. Run `make builddeb` and upload the resulting Debian package to a new
   [GitHub release](https://github.com/Yelp/dumb-init/releases)
