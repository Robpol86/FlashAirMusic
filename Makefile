export NAME := $(shell ./setup.py --name)
export SUMMARY := $(shell ./setup.py --description |sed 's/\.$$//')
export URL := $(shell ./setup.py --url)
export VERSION := $(shell ./setup.py --version)

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
	cat DockerfileTemplates/DockerfileFedoraBuild |envsubst > Dockerfile
	docker build -t build/$(MODE) .
	docker run -v ${PWD}:/build build/$(MODE) make
	cat DockerfileTemplates/DockerfileFedoraRun |envsubst > Dockerfile
	docker build -t run/$(MODE) .
	rm Dockerfile

docker-run: DOCKER_CONTAINER_ID=$$(docker ps |grep run/$(MODE) |awk '{print $$1}')
docker-run:
	docker run -v ${PWD}:/build:ro run/$(MODE) make docker-rpmlint
	docker run -v ${PWD}/tests:/build/tests:ro run/$(MODE) su -m user -c "py.test-3 tests"
	docker run -v ${PWD}:/build:ro -v /sys/fs/cgroup -v /run -v /tmp --privileged -dti run/$(MODE)
	docker logs $(DOCKER_CONTAINER_ID)
	docker exec -ti $(DOCKER_CONTAINER_ID) make docker-rpmtest

docker-rpmlint:
	systemd-analyze verify $(NAME).service
	rpmlint $(NAME)
	$(NAME) --help
	test $$(rpm -q $(NAME) --queryformat '%{NAME}') == "$(NAME)"
	test "$$(rpm -q $(NAME) --queryformat '%{SUMMARY}')" == "$(SUMMARY)"
	test "$$(rpm -q $(NAME) --queryformat '%{URL}')" == "$(URL)"
	test $$(rpm -q $(NAME) --queryformat '%{VERSION}') == "$(VERSION)"
	test $$($(NAME) --version) == "$(VERSION)"

docker-rpmtest:
	! test -f /home/$(NAME)/fam_working_dir/song1.mp3
	! test -f /home/$(NAME)/fam_working_dir/song2.mp3
	! test -f /var/log/$(NAME)/$(NAME).log

	systemctl start $(NAME).service
	until systemctl status -l $(NAME).service; do sleep 1; done

	cp tests/1khz_sine.flac /home/$(NAME)/fam_music_source/song1.flac
	cp tests/1khz_sine.mp3 /home/$(NAME)/fam_music_source/song2.mp3
	until grep "Done converting 2 file(s) (0 failed)." /var/log/$(NAME)/$(NAME).log; do sleep 1; done
	ffprobe /home/$(NAME)/fam_working_dir/song1.mp3
	ffprobe /home/$(NAME)/fam_working_dir/song2.mp3

	systemctl stop $(NAME).service
	until ! systemctl status -l $(NAME).service; do sleep 1; done
	grep "Shutting down" /var/log/$(NAME)/$(NAME).log
