#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='django-synchro',
    description='Django app for database data synchronization.',
    long_description=open('README.rst').read(),
    version='0.7',
    author='Jacek Tomaszewski',
    author_email='jacek.tomek@gmail.com',
    url='https://github.com/zlorf/django-synchro',
    license='MIT',
    install_requires=(
        'django-dbsettings>=0.7',
        'django>=1.7',
    ),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
        'Framework :: Django :: 1.7',
        'Framework :: Django :: 1.8',
        'Framework :: Django :: 1.9',
        'Framework :: Django :: 1.10',
        'Framework :: Django :: 1.11',
    ],
    packages=find_packages(),
    include_package_data = True,
)
