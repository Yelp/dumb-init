import os.path
import subprocess
import tempfile
from distutils.command.build import build as orig_build
from distutils.core import Command

from setuptools import Distribution
from setuptools import Extension
from setuptools import setup
from setuptools.command.install import install as orig_install
from setuptools_rust import Binding, RustExtension


try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel

    class bdist_wheel(_bdist_wheel):

        def finalize_options(self):
            _bdist_wheel.finalize_options(self)
            # Mark us as not a pure python package
            self.root_is_pure = False

        def get_tag(self):
            python, abi, plat = _bdist_wheel.get_tag(self)
            # We don't contain any python source
            python, abi = 'py2.py3', 'none'
            return python, abi, plat
except ImportError:
    bdist_wheel = None

class install(orig_install):
    sub_commands = orig_install.sub_commands + [
        ('install_rexe', None),
    ]


class install_rexe(Command):
    description = 'install Rust executables'
    outfiles = ()

    def initialize_options(self):
        self.build_dir = self.install_dir = None

    def finalize_options(self):
        # this initializes attributes based on other commands' attributes
        self.set_undefined_options('install_lib', ('build_dir', 'build_dir'))
        self.set_undefined_options(
            'install', ('install_scripts', 'install_dir'),
        )

    def run(self):
        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

    def get_outputs(self):
        return self.outfiles


setup(
    name='dumb-init',
    description='Simple wrapper script which proxies signals to a child',
    version=open('VERSION').read().strip(),
    author='Yelp',
    url='https://github.com/Yelp/dumb-init/',
    platforms='linux',
    rust_extensions=[RustExtension("dumb-init", binding=Binding.Exec)],
    cmdclass={
        'bdist_wheel': bdist_wheel,
        'install': install,
        'install_rexe': install_rexe,
    }
)
