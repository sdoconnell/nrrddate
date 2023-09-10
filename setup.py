#!/usr/bin/env python3

from setuptools import setup

setup(
    name="nrrddate",
    version="0.0.4",
    description="A terminal-based calendar for nerds.",
    author="Sean O'Connell",
    author_email="sean@sdoconnell.net",
    url="https://github.com/sdoconnell/nrrddate",
    license="MIT",
    python_requires='>=3.8',
    packages=['nrrddate'],
    install_requires=[
        "tzlocal>=2.1",
        "icalendar>=4.0.9",
        "pyyaml>=5.4",
        "rich>=10.2",
        "watchdog>=2.1",
        "python-dateutil>=2.8"
    ],
    include_package_data=True,
    entry_points={
        "console_scripts": "nrrddate=nrrddate.nrrddate:main"
    },
    keywords='cli calendar utility',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English',
        'Operating System :: POSIX',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.8',
        'Topic :: Office/Business',
        'Topic :: Utilities'
    ]
)
