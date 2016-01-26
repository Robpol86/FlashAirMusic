export NAME = $(shell ./setup.py --name)
export SUMMARY = $(shell ./setup.py --description |sed 's/\.$$//')
export URL = $(shell ./setup.py --url)
export VERSION = $(shell ./setup.py --version)

all: clean pre sdist rpm

clean:
	rm -rf $(HOME)/rpmbuild
	rm -f $(NAME)-$(VERSION)-*.rpm

pre:
	rpmdev-setuptree

sdist:
	./setup.py sdist
	mv dist/$(NAME)-$(VERSION).tar.gz $(HOME)/rpmbuild/SOURCES/

rpm:
	cp $(NAME).spec $(HOME)/rpmbuild/SPECS/
	rpmbuild -ba $(NAME).spec
	mv $(HOME)/rpmbuild/RPMS/*/$(NAME)-$(VERSION)-*.rpm .

install:
	dnf -qy remove $(NAME) || true
	dnf -y install $(NAME)-$(VERSION)-*.rpm

docker-rpmtest: install
	rpmlint $(NAME)
	$(NAME) --help
	test $$(rpm -q $(NAME) --queryformat '%{NAME}') == "$(NAME)"
	test "$$(rpm -q $(NAME) --queryformat '%{SUMMARY}')" == "$(SUMMARY)"
	test "$$(rpm -q $(NAME) --queryformat '%{URL}')" == "$(URL)"
	test $$(rpm -q $(NAME) --queryformat '%{VERSION}') == "$(VERSION)"
	test $$($(NAME) --version) == "$(VERSION)"

docker-build-images:
	docker pull robpol86/rpmfusion-$(MODE)
	cat DockerfileRPMBuild |envsubst > Dockerfile
	docker build -t local/$(MODE) .
	rm Dockerfile

docker-run-both:
	docker run -v ${PWD}:/build local/$(MODE) make
	docker run -v ${PWD}:/build:ro -w /build robpol86/rpmfusion-$(MODE) make docker-rpmtest
