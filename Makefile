.PHONY: build clean builddeb builddeb-docker itest_lucid itest_precise itest_trusty
build:
	$(CC) -static -Wall -Werror -o dumb-init dumb-init.c

clean:
	rm -rf dumb-init dist

builddeb:
	rm -rf dist && mkdir -p dist
	debuild -us -uc -b
	mv ../dumb-init_*.deb dist

builddeb-docker: docker-image
	docker run -v $(PWD):/mnt dumb-init-build

docker-image:
	docker build -t dumb-init-build .

itest_lucid: docker_build

itest_precise: docker_build

itest_trusty: docker_build
