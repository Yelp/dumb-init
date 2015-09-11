CFLAGS=-std=gnu99 -static -Wall -Werror

TEST_PACKAGE_DEPS := python python-pip

DOCKER_RUN_TEST := docker run -v $(PWD):/mnt:ro
DOCKER_DEB_TEST := sh -euxc ' \
	apt-get update \
	&& apt-get install -y --no-install-recommends $(TEST_PACKAGE_DEPS) \
	&& dpkg -i /mnt/dist/*.deb \
	&& tmp=$$(mktemp -d) \
	&& cp -r /mnt/* "$$tmp" \
	&& cd "$$tmp" \
	&& pip install pytest \
	&& py.test tests/ \
	&& exec dumb-init /mnt/tests/test-zombies \
'
DOCKER_PYTHON_TEST := sh -uexc ' \
	apt-get update \
	&& apt-get install -y --no-install-recommends python-pip build-essential $(TEST_PACKAGE_DEPS) \
	&& tmp=$$(mktemp -d) \
	&& cp -r /mnt/* "$$tmp" \
	&& cd "$$tmp" \
	&& python setup.py clean \
	&& python setup.py sdist \
	&& pip install -vv dist/*.tar.gz \
	&& pip install pytest \
	&& py.test tests/ \
	&& exec dumb-init /mnt/tests/test-zombies \
'

.PHONY: build
build:
	$(CC) $(CFLAGS) -o dumb-init dumb-init.c

.PHONY: clean
clean: clean-tox
	rm -rf dumb-init dist/ *.deb

.PHONY: clean-tox
clean-tox:
	rm -rf .tox

.PHONY: builddeb
builddeb:
	debuild -us -uc -b
	rm -rf dist && mkdir dist
	mv ../dumb-init_*.deb dist/

.PHONY: builddeb-docker
builddeb-docker: docker-image
	docker run -v $(PWD):/mnt dumb-init-build

.PHONY: docker-image
docker-image:
	docker build -t dumb-init-build .

.PHONY: test
test:
	tox

.PHONY: install-hooks
install-hooks:
	tox -e pre-commit -- install -f --install-hooks

.PHONY: itest itest_lucid itest_precise itest_trusty itest_wheezy itest_jessie itest_stretch
itest: itest_lucid itest_precise itest_trusty itest_wheezy itest_jessie itest_stretch

itest_lucid: _itest-ubuntu-lucid
itest_precise: _itest-ubuntu-precise
itest_trusty: _itest-ubuntu-trusty
itest_wheezy: _itest-debian-wheezy
itest_jessie: _itest-debian-jessie
itest_stretch: _itest-debian-stretch

_itest-%: _itest_deb-% _itest_python-%
	@true

_itest_python-%:
	$(eval DOCKER_IMG := $(shell echo $@ | cut -d- -f2- | sed 's/-/:/'))
	$(DOCKER_RUN_TEST) $(DOCKER_IMG) $(DOCKER_PYTHON_TEST)

_itest_deb-%: builddeb-docker
	$(eval DOCKER_IMG := $(shell echo $@ | cut -d- -f2- | sed 's/-/:/'))
	$(DOCKER_RUN_TEST) $(DOCKER_IMG) $(DOCKER_DEB_TEST)
