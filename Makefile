DOCKER_RUN_TEST := docker run -v $(PWD):/mnt:ro
DOCKER_DEB_TEST := sh -c 'apt-get update && \
	apt-get install -y --no-install-recommends procps && \
	dpkg -i /mnt/dist/*.deb && cd /mnt && ./test'
DOCKER_PYTHON_TEST := sh -c 'apt-get update && \
	apt-get install -y --no-install-recommends python-pip build-essential procps && \
	pip install /mnt && cd /mnt && ./test'

.PHONY: build
build:
	$(CC) -static -Wall -Werror -o dumb-init dumb-init.c

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
	@true
itest_precise: _itest-ubuntu-precise
	@true
itest_trusty: _itest-ubuntu-trusty
	@true
itest_wheezy: _itest-debian-wheezy
	@true
itest_jessie: _itest-debian-jessie
	@true
itest_stretch: _itest-debian-stretch
	@true

_itest-%: _itest_deb-% _itest_python-%
	@true

_itest_python-%:
	$(eval DOCKER_IMG := $(shell echo $@ | cut -d- -f2 | sed 's/-/:/'))
	$(DOCKER_RUN_TEST) $(DOCKER_IMG) $(DOCKER_PYTHON_TEST)

_itest_deb-%:
	$(eval DOCKER_IMG := $(shell echo $@ | cut -d- -f2 | sed 's/-/:/'))
	$(DOCKER_RUN_TEST) $(DOCKER_IMG) $(DOCKER_DEB_TEST)
