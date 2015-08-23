from setuptools import find_packages, setup

from pip.req import parse_requirements


def get_version():
    import imp

    pkg_meta = imp.load_source('_pkg_meta', 'biloba/_pkg_meta.py')

    return pkg_meta.version


def get_requirements(filename):
    try:
        from pip.download import PipSession

        session = PipSession()
    except ImportError:
        session = None

    reqs = parse_requirements(filename, session=session)

    return [str(r.req) for r in reqs]


setup_args = dict(
    name='biloba',
    version=get_version(),
    maintainer='Nick Joyce',
    maintainer_email='nick@boxdesign.co.uk',
    description=(
        'Provides gevent primitives to orchestrate different '
        'orthogonal servers and services together.'
    ),
    url='https://github.com/njoyce/biloba',
    packages=find_packages(),
    install_requires=get_requirements('requirements.txt'),
    tests_require=get_requirements('requirements_dev.txt'),
)


if __name__ == '__main__':
    setup(**setup_args)
