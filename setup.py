#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='django-synchro',
    description='Django app for database data synchronization.',
    long_description=open('README.rst').read(),
    version='0.4.2',
    author='Jacek Tomaszewski',
    author_email='jacek.tomek@gmail.com',
    url='https://github.com/zlorf/django-synchro',
    license='MIT',
    install_requires=(
        'django-dbsettings>=0.1',
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
