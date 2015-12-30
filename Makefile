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
