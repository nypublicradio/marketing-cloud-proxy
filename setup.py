"""
Salesforce Marketing Cloud proxy to simplify newsletter subscription
"""
from setuptools import setup

setup(
    author='NYPR Digital',
    author_email='digitalops@nypublicradio.org',
    description=__doc__,
    entry_points={
        'distutils.commands': [
            'requirements = nyprsetuptools:InstallRequirements',
            'test = nyprsetuptools:PyTest',
            'test_requirements = nyprsetuptools:InstallTestRequirements',
            'deploy = nyprsetuptools:LambdaDeploy',
        ],
        'distutils.setup_keywords': [
            'requirements = nyprsetuptools:setup_keywords',
            'test = nyprsetuptools:setup_keywords',
            'test_requirements = nyprsetuptools:setup_keywords',
            'deploy = nyprsetuptools:setup_keywords',
        ],
    },
    install_requires=[
        'PyJWT=1.7.1',
        'Salesforce-FuelSDK'
        'flask',
    ],
    license='BSD',
    long_description=__doc__,
    name='marketing-cloud-proxy',
    package_data={},
    scripts=[],
    setup_requires=[
        'nyprsetuptools@https://github.com/nypublicradio/nyprsetuptools/tarball/master'
    ],
    tests_require=[
        'moto',
        'pytest',
        'pytest-cov',
        'pytest-env',
        'pytest-flake8',
        'pytest-mock',
        'pytest-sugar',
    ],
    url='https://github.com/nypublicradio/marketing-cloud-proxy',
    version='0.0.0',
    zip_safe=True,
)
