"""A setuptools based setup module.

See:
    https://packaging.python.org/en/latest/distributing.html
    https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

# Load the hamster_briefs module. If it's already installed,
# it doesn't matter, since Python looks locally first.
from hamster_briefs import version_hamster

# I [lb] don't quite get the version postfix -- it's required, otherwise pip
# won't find the project on GitHub. The confusing part seems to be that the
# version doesn't matter. All of these projects are version 0.1.0 (at least
# in setup.py), but I've never tagged them in GitHub. But with the -10.0,
# or -1.0, -99999, or -2, they all work; but without the -n postfix, they
# don't work.
# Ref: GitHub API: Get archive link
#   https://developer.github.com/v3/repos/contents/#get-archive-link
# Group discuss:
#   https://groups.google.com/forum/#!topic/pypa-dev/tJ6HHPQpyJ4
#
# But whatever. The `dependency_links` feature is deprecated. E.g., don't do:
#
#       pip install -v --user --process-dependency-links -e .
#
# but use a requirements.txt instead.
dependency_links_github=[
    'https://github.com/landonb/pyoiler-argparse/tarball/master#egg=pyoiler-argparse-10.0',
    'https://github.com/landonb/pyoiler-inflector/tarball/master#egg=pyoiler-inflector-1.0',
    'https://github.com/landonb/pyoiler-logging/tarball/master#egg=pyoiler-logging-99999',
    'https://github.com/landonb/pyoiler-timedelta/tarball/master#egg=pyoiler-timedelta-2',
]

# Get the long description from the README file
here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='hamster-briefs',

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # https://packaging.python.org/en/latest/single_source_version.html
    version=version_hamster.SCRIPT_VERS,

    description="hamster.db analysis and reporting tool",
    long_description=long_description,

    # The project's main homepage.
    url='https://github.com/landonb/hamster-briefs',

    # Author details
    author='Landon Bouma',
    author_email='retrosoft@gmail.com',

    # Choose your license
    #license='MIT',
    license='GPLv3',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 3 - Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',

        # Pick your license as you wish (should match "license" above)
        #'License :: OSI Approved :: MIT License',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        #'Programming Language :: Python :: 2',
        #'Programming Language :: Python :: 2.6',
        #'Programming Language :: Python :: 2.7',
        #'Programming Language :: Python :: 3',
        #'Programming Language :: Python :: 3.3',
        #'Programming Language :: Python :: 3.4',
        # Needs py3.5's subprocess.run.
        'Programming Language :: Python :: 3.5',
    ],

    # What does your project relate to?
    keywords='inflector pyoilerplate development',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),

    # Alternatively, if you want to distribute just a my_module.py, uncomment
    # this:
    #   py_modules=["my_module"],

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    #   https://packaging.python.org/en/latest/requirements.html
    install_requires=[
        'pyoiler_argparse',
        'pyoiler_inflector',
        'pyoiler_logging',
        'pyoiler_timedelta',
    ],

    # See above. Use requirements.txt, not dependency_links.
    #dependency_links=dependency_links_github,

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['check-manifest'],
        'test': ['coverage'],
    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    #package_data={
    #    'sample': ['package_data.dat'],
    #},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files # noqa
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    #data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    #
    # [lb]: This installs to /usr/local/bin, e.g., if you don't sudo:
    #   Installing pyoiler_inflector script to /usr/local/bin
    #   error: [Errno 13] Permission denied: '/usr/local/bin/pyoiler_inflector'
    entry_points={
        'console_scripts': [
            'hamster-briefs=hamster_briefs.hamster_briefs:main',
            'hamster-love=hamster_briefs:run_hamster_love',
            'transform-brief=hamster_briefs.transform_brief:main',
        ],
    },
)

