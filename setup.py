#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='django-synchro',
    description='Django app for database data synchronization.',
    long_description=open('README.rst').read(),
    version='0.8',
    author='Jacek Tomaszewski',
    author_email='jacek.tomek@gmail.com',
    url='https://github.com/zlorf/django-synchro',
    license='MIT',
    install_requires=(
        'django-dbsettings>=0.11.0',
        'django>=2.0',
    ),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Framework :: Django',
        'Framework :: Django :: 2.0',
        'Framework :: Django :: 2.1',
        'Framework :: Django :: 2.2',
    ],
    packages=find_packages(),
    include_package_data = True,
    zip_safe=False,
)
