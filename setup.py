#!/usr/bin/env python3
"""Setup script for the project."""

from __future__ import print_function

import codecs
import os

from setuptools import find_packages, setup


def readme():
    """Try to read README.rst or return empty string if failed.

    :return: File contents.
    :rtype: str
    """
    path = os.path.realpath(os.path.join(os.path.dirname(__file__), 'README.rst'))
    handle = None
    try:
        handle = codecs.open(path, encoding='utf-8')
        return handle.read(131072)
    except IOError:
        return ''
    finally:
        getattr(handle, 'close', lambda: None)()


setup(
    author='@Robpol86',
    author_email='robpol86@gmail.com',
    classifiers=['Private :: Do Not Upload'],
    description="Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.",
    entry_points={'console_scripts': ['FlashAirMusic = flash_air_music.__main__:entry_point']},
    extras_require=dict(docoptcfg=['docoptcfg']),
    install_requires=['docopt', 'mutagen', 'requests'],
    keywords='FlashAir flac music mp3 WiFi',
    license='MIT',
    long_description=readme(),
    name='FlashAirMusic',
    packages=find_packages(exclude=['tests']),
    url='https://github.com/Robpol86/FlashAirMusic',
    version='0.0.1',
    zip_safe=True,
)
