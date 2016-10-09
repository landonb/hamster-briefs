# Do we need a shebang here?
# vim:tw=0:ts=4:sw=4:noet
#
# FIXME: 2016-02-16: This setup script is untested...
#        Here are some possibly useful notes:
#
# To generate
#
#  python setup.py sdist
#
# /usr/lib/python2.7/dist-packages/setuptools/command/
#
# https://pypi.python.org/pypi/setuptools
#
# easy_install http://example.com/path/to/MyPackage-1.2.3.tgz
# easy_install /my_downloads/OtherPackage-3.2.1-py2.3.egg
# cd path/to/package && easy_install .
#
#https://pip.pypa.io/en/latest/reference/pip_install.html
#pip install [options] [-e] <local project path> ...
# 

from setuptools import setup

setup(
	name='hamster_briefs',
	version='0.1.0',
	author='Landon Bouma',
	author_email='landonb@retrosoft.com',
	packages=['hamster_briefs',],
	#scripts=['bin/nothing_here.py',],
	url='https://github.com/landonb/hamster_briefs',
	license='LICENSE.txt',
	description='hamster.db analysis tool',
	long_description=open('README.rst').read(),
#/usr/lib/python2.7/distutils/dist.py:267: UserWarning: Unknown distribution option: 'install_requires'
	install_requires=[
	],
	dependency_links = [
	],
)

