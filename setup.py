#!/usr/bin/env python
"""Setup script for the project."""

from __future__ import print_function

from setuptools import find_packages, setup


setup(
    author='@Robpol86',
    author_email='robpol86@gmail.com',
    classifiers=['Private :: Do Not Upload'],
    description="Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.",
    entry_points={'console_scripts': ['FlashAirMusic = flash_air_music.__main__:entry_point']},
    install_requires=['docopt==0.6.2', 'PyYAML==3.11', 'requests==2.9.1'],
    keywords='FlashAir flac music mp3 WiFi',
    license='MIT',
    name='FlashAirMusic',
    packages=find_packages(exclude=['tests']),
    url='https://github.com/Robpol86/FlashAirMusic',
    version='0.0.1',
    zip_safe=True,
)
