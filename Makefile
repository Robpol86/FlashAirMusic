export MODE_MAJOR ?= $(shell python -c "import os; print(os.environ.get('MODE', '').split(':')[0])")
export NAME ?= $(shell ./setup.py --name)
export SUMMARY ?= $(shell ./setup.py --description |sed 's/\.$$//')
export URL ?= $(shell ./setup.py --url)
export VERSION ?= $(shell ./setup.py --version)

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
	spectool -g $(NAME).spec -C $(HOME)/rpmbuild/SOURCES
	rpmbuild -ba $(NAME).spec
	mv $(HOME)/rpmbuild/RPMS/*/$(NAME)-$(VERSION)-*.rpm .

install:
	dnf -qy remove $(NAME) || true
	dnf -y install $(NAME)-$(VERSION)-*.rpm

docker-build:
	cat DockerfileTemplates/Dockerfile_$(MODE_MAJOR)_Build |envsubst > Dockerfile
	docker build -t build/$(MODE) .
	docker run -v ${PWD}:/build build/$(MODE) make
	cat DockerfileTemplates/Dockerfile_$(MODE_MAJOR)_Lint |envsubst > Dockerfile
	docker build -t lint/$(MODE) .
	cat DockerfileTemplates/Dockerfile_$(MODE_MAJOR)_Run |envsubst > Dockerfile
	docker build -t run/$(MODE) .
	rm Dockerfile

docker-test: DOCKER_CONTAINER_ID=$$(docker ps |grep run/$(MODE) |awk '{print $$1}')
docker-test:
	docker run -v ${PWD}:/build:ro lint/$(MODE) make docker-internal-lint
	docker run -v ${PWD}/tests:/build/tests:ro lint/$(MODE) su -m user -c "py.test-3 tests"
	docker run -v ${PWD}:/build:ro --privileged -dti run/$(MODE)
	docker exec -ti $(DOCKER_CONTAINER_ID) make docker-internal-run

docker-internal-lint:
	systemd-analyze verify $(NAME).service
	rpmlint $(NAME)
	$(NAME) --help
	test $$(rpm -q $(NAME) --queryformat '%{NAME}') == "$(NAME)"
	test "$$(rpm -q $(NAME) --queryformat '%{SUMMARY}')" == "$(SUMMARY)"
	test "$$(rpm -q $(NAME) --queryformat '%{URL}')" == "$(URL)"
	test $$(rpm -q $(NAME) --queryformat '%{VERSION}') == "$(VERSION)"
	test $$($(NAME) --version) == "$(VERSION)"

docker-internal-run: PATH_LOG := /var/log/$(NAME)/$(NAME).log
docker-internal-run: PATH_SONG1 := /home/$(NAME)/fam_working_dir/song1.mp3
docker-internal-run: PATH_SONG2 := /home/$(NAME)/fam_working_dir/song2.mp3
docker-internal-run:
	! test -f $(PATH_SONG1)
	! test -f $(PATH_SONG2)
	! test -f $(PATH_LOG)

	mkdir /home/$(NAME)/fam_music_source
	systemctl start $(NAME).service
	systemctl status -l $(NAME).service
	for i in {1..5}; do test -f $(PATH_LOG) && break; sleep 1; done
	grep "Running main loop." $(PATH_LOG)

	cp tests/1khz_sine.flac /home/$(NAME)/fam_music_source/song1.flac
	cp tests/1khz_sine.mp3 /home/$(NAME)/fam_music_source/song2.mp3
	for i in {1..400}; do grep "Done converting" $(PATH_LOG) && break; sleep 1; done
	grep "Done converting 2 file(s) (0 failed)." $(PATH_LOG)
	ffprobe $(PATH_SONG1)
	ffprobe $(PATH_SONG2)

	systemctl stop $(NAME).service
	! systemctl status -l $(NAME).service
	ps aux |grep -v $(NAME)
	grep "Shutting down" $(PATH_LOG)
	cat $(PATH_LOG)
