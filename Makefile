export NAME = $(shell ./setup.py --name)
export SUMMARY = $(shell ./setup.py --description)
export URL = $(shell ./setup.py --url)
export VERSION = $(shell ./setup.py --version)


.PHONY: all
all: clean pre sdist rpm


.PHONY: clean
clean:
	rm -rf $(HOME)/rpmbuild


.PHONY: pre
pre:
	rpmdev-setuptree


.PHONY: sdist
sdist:
	./setup.py sdist
	mv dist/$(NAME)-$(VERSION).tar.gz $(HOME)/rpmbuild/SOURCES/


.PHONY: rpm
rpm:
	cp $(NAME).spec $(HOME)/rpmbuild/SPECS/
	rpmbuild -ba $(NAME).spec


.PHONY: docker-rpmbuild
docker-rpmbuild: all
	cp -v $(HOME)/rpmbuild/RPMS/*/$(NAME)-$(VERSION)-*.rpm .


.PHONY: docker-rpmtest
docker-rpmtest:
	dnf install -y $(NAME)-$(VERSION)-*.rpm
	$(NAME) --help
	test $$(rpm -q $(NAME) --queryformat '%{NAME}') == "$(NAME)"
	test "$$(rpm -q $(NAME) --queryformat '%{SUMMARY}')" == "$(SUMMARY)"
	test "$$(rpm -q $(NAME) --queryformat '%{URL}')" == "$(URL)"
	test $$(rpm -q $(NAME) --queryformat '%{VERSION}') == "$(VERSION)"
	test $$($(NAME) --version) == "$(VERSION)"


.PHONY: docker-build-images
docker-build-images:
	docker pull $(MODE)
	cat Dockerfile |envsubst > DockerfileParsed
	docker build -t local/$(MODE) -f DockerfileParsed .
	rm DockerfileParsed


.PHONY: docker-run-both
docker-run-both:
	docker run -v ${PWD}:/build local/$(MODE) make docker-rpmbuild
	docker run -v ${PWD}:/build:ro -w /build $(MODE) /bin/sh -c "dnf install -y make && make docker-rpmtest"
