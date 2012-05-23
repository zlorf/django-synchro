#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='django-synchro',
    description='Django app for database data synchronization.',
    version='0.2',
    maintainer="Jacek Tomaszewski",
    maintainer_email="jacek.tomek@gmail.com",
    install_requires=(
        'django-dbsettings',
        'django>=1.3',
    ),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
    ],
    packages=find_packages(),
    include_package_data = True,
)
