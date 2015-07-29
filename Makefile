.PHONY: build
build:
	gcc -static -Wall -Werror -o dumb-init dumb-init.c

clean:
	rm -rf dumb-init
