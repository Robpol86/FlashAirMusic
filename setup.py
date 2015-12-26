#!/usr/bin/env python
"""Setup script for the project."""

from __future__ import print_function

from setuptools import find_packages, setup


setup(
    author='@Robpol86',
    author_email='robpol86@gmail.com',
    classifiers=['Private :: Do Not Upload'],
    description="Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.",
    install_requires=[],
    keywords='FlashAir flac music mp3 WiFi',
    license='MIT',
    name='FlashAirMusic',
    packages=find_packages(exclude='tests'),
    url='https://github.com/Robpol86/FlashAirMusic',
    version='0.0.1',
    zip_safe=True,
)
