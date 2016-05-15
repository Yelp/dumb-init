import os.path
from distutils.command.build import build as orig_build
from distutils.core import Command

from setuptools import Distribution
from setuptools import Extension
from setuptools import setup
from setuptools.command.install import install as orig_install


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


class ExeDistribution(Distribution):
    c_executables = ()


class build(orig_build):
    sub_commands = orig_build.sub_commands + [
        ('build_cexe', None),
    ]


class install(orig_install):
    sub_commands = orig_install.sub_commands + [
        ('install_cexe', None),
    ]


class install_cexe(Command):
    description = 'install C executables'
    outfiles = ()

    def initialize_options(self):
        self.build_dir = self.install_dir = None

    def finalize_options(self):
        # this initializes attributes based on other commands' attributes
        self.set_undefined_options('build', ('build_scripts', 'build_dir'))
        self.set_undefined_options(
            'install', ('install_scripts', 'install_dir'))

    def run(self):

        self.outfiles = self.copy_tree(self.build_dir, self.install_dir)

    def get_outputs(self):
        return self.outfiles


class build_cexe(Command):
    description = 'build C executables'

    def initialize_options(self):
        self.build_scripts = None
        self.build_temp = None

    def finalize_options(self):
        self.set_undefined_options(
            'build',
            ('build_scripts', 'build_scripts'),
            ('build_temp', 'build_temp'),
        )

    def run(self):
        # stolen and simplified from distutils.command.build_ext
        from distutils.ccompiler import new_compiler

        compiler = new_compiler(verbose=True)

        for exe in self.distribution.c_executables:
            objects = compiler.compile(
                exe.sources,
                output_dir=self.build_temp,
            )
            compiler.link_executable(
                objects,
                exe.name,
                output_dir=self.build_scripts,
                extra_postargs=exe.extra_link_args,
            )

    def get_outputs(self):
        return [
            os.path.join(self.build_scripts, exe.name)
            for exe in self.distribution.c_executables
        ]


setup(
    name='dumb-init',
    description='Simple wrapper script which proxies signals to a child',
    version=open('VERSION').read().strip(),
    author='Yelp',
    url='https://github.com/Yelp/dumb-init/',
    platforms='linux',
    c_executables=[
        Extension(
            'dumb-init',
            ['dumb-init.c'],
            extra_link_args=['-static'],
        ),
    ],
    cmdclass={
        'bdist_wheel': bdist_wheel,
        'build': build,
        'build_cexe': build_cexe,
        'install': install,
        'install_cexe': install_cexe,
    },
    distclass=ExeDistribution,
)
