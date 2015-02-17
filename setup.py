from setuptools import find_packages, setup

from pip.req import parse_requirements


def get_version():
    import imp

    filename = 'biloba/_meta.py'

    with open(filename, 'rb') as fp:
        mod = imp.load_source('_meta', filename, fp)

    return mod.version


def get_requirements(filename):
    try:
        from pip.download import PipSession

        session = PipSession()
    except ImportError:
        session = None

    reqs = parse_requirements(filename, session=session)

    return [str(r.req) for r in reqs]


def get_install_requires():
    return get_requirements('requirements.txt')


def get_test_requires():
    return get_requirements('requirements_dev.txt')


setup_args = dict(
    name='biloba',
    version=get_version(),
    maintainer='Nick Joyce',
    description=(
        'Provides gevent primitives to orchestrate different'
        'orthogonal servers and services together.'
    ),
    url='https://github.com/njoyce/biloba',
    maintainer_email='nick@boxdesign.co.uk',
    packages=find_packages(),
    install_requires=get_install_requires(),
    tests_require=get_test_requires(),
)


if __name__ == '__main__':
    setup(**setup_args)
