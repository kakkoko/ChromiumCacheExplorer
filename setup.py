#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='ChromiumCacheExplorer',
    version='0.1',
    author='kakkoko',
    author_email='kakkoko@pushf.jp',
    description='explore caches of Chromium browser',
    url='https://github.com/kakkoko/ChromiumCacheExplorer',
    classifiers=[
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Browsers',
        'License :: OSI Approved :: MIT License',
        'Development Status :: 4 - Beta',
    ],
    packages=find_packages(),
)
