# $MODE, $NAME, and others are defined in .travis.yml and Makefile by envsubst.

FROM robpol86/rpmdevtools-$MODE
MAINTAINER Robpol86 <robpol86@gmail.com>

VOLUME /build
WORKDIR /build

ENV NAME="$NAME" SUMMARY="$SUMMARY" URL="$URL" VERSION="$VERSION"
ADD $NAME.spec $NAME.spec
RUN dnf builddep -y --spec $NAME.spec && rm $NAME.spec
