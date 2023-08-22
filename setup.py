"""
Salesforce Marketing Cloud proxy to simplify newsletter subscription
"""
from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    author='NYPR Digital',
    author_email='digitalops@nypublicradio.org',
    description=__doc__.strip(),
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
        'PyJWT==2.4.0',
        'Salesforce-FuelSDK @ git+https://github.com/nypublicradio/FuelSDK-Python.git',
        'Werkzeug==1.0.1', # for compatitility with Flask 1.x
        'boto3~=1.21',
        'lxml==4.9.2',
        'flask==1.1.4',
        'markupsafe==2.0.1',
        'python-dotenv',
        'pytz',
        'requests',
        'sentry-sdk[flask]',
        'serverless-wsgi<2.0', # for compatibility with Werkzeug 1.x
        'setuptools==57.5.0',
        'simple-salesforce',
    ],
    license='BSD',
    long_description=long_description,
    long_description_content_type="text/markdown",
    name='marketing-cloud-proxy',
    package_data={},
    packages=['marketing_cloud_proxy'],
    scripts=[],
    setup_requires=[
        'nyprsetuptools @ git+https://github.com/nypublicradio/nyprsetuptools@master#egg=nyprsetuptools'
    ],
    tests_require=[
        'dotmap',
        'moto<4.0.0',
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
