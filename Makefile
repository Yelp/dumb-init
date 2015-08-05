DOCKER_TEST := sh -c 'dpkg -i /mnt/dist/*.deb && cd /mnt/test && ./test'

.PHONY: build
build:
	$(CC) -static -Wall -Werror -o dumb-init dumb-init.c

.PHONY: clean
clean:
	rm -rf dumb-init dist/ *.deb

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

.PHONY: itest itest_lucid itest_precise itest_trusty itest_wheezy itest_jessie itest_stretch
itest: itest_lucid itest_precise itest_trusty itest_wheezy itest_jessie itest_stretch

itest_lucid: builddeb-docker
	docker run -v $(PWD):/mnt:ro ubuntu:lucid \
		sh -ec "apt-get -y install timeout; $(DOCKER_TEST)"

itest_precise: builddeb-docker
	docker run -v $(PWD):/mnt:ro ubuntu:precise $(DOCKER_TEST)

itest_trusty: builddeb-docker
	docker run -v $(PWD):/mnt:ro ubuntu:trusty $(DOCKER_TEST)

itest_wheezy: builddeb-docker
	docker run -v $(PWD):/mnt:ro debian:wheezy $(DOCKER_TEST)

itest_jessie: builddeb-docker
	docker run -v $(PWD):/mnt:ro debian:jessie $(DOCKER_TEST)

itest_stretch: builddeb-docker
	docker run -v $(PWD):/mnt:ro debian:stretch $(DOCKER_TEST)
