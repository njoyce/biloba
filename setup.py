from setuptools import find_packages, setup

from pip.req import parse_requirements


def get_version():
    import imp

    with open('biloba/_meta.py', 'rb') as fp:
        mod = imp.load_source('_meta', 'biloba', fp)

    return mod.version


def get_requirements(filename):
    reqs = parse_requirements(filename)

    return [str(r.req) for r in reqs]


def get_install_requires():
    return get_requirements('requirements.txt')


def get_test_requires():
    return get_requirements('requirements_dev.txt')


setup_args = dict(
    name='biloba',
    version=get_version(),
    maintainer='Nick Joyce',
    maintainer_email='nick@boxdesign.co.uk',
    packages=find_packages(),
    install_requires=get_install_requires(),
    tests_require=get_test_requires(),
)


if __name__ == '__main__':
    setup(**setup_args)
