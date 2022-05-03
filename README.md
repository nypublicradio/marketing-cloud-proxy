# marketing-cloud-proxy

A lambda / Flask app that handles communication with our Salesforce CRM and
Marketing Cloud email service provider. It currently includes endpoints to
`subscribe` new users and return all `lists`.


## Installation

1\. Make a virtualenv for the project

The easiest way with Python 3 is:

```bash
# From the project's base directory

python3 -m venv .venv

source .venv/bin/activate
```

2\. Install app dependencies

```bash
pip install -e .
```

3\. Install test dependencies

```bash
python setup.py test_requirements
```

4\. Copy `.env.sample` to `.env` and update the variables.

Notes on where to get each variable is commented inside the env sample.

5\. Run the flask app

```bash
FLASK_APP=marketing_cloud_proxy/app.py  FLASK_ENV=development python -m flask run
```

**Note:** If you ever get hung up on the installation of any project, always take a look at the `build` step in `circle.yml`, because those steps are known to work to build the app and run tests within Circle CI.

## Tests

Assuming test requirements have been installed, run `pytest`

## Development

Just a general note, this app has two external dependencies that are somewhat difficult to setup to access locally.

First is DynamoDB, which is where the Marketing Cloud auth token is stored. This requires AWS credentials that have access to DynamoDB and to the table where the key is stored.

Second is the connection to Marketing Cloud itself, which requires a number of MC-specific environment variables as well as a valid External Key for whatever data extension is being accessed. The `.env.sample` file has notes on where to get each key.

The fastest way to develop against this repo without having access to those two external resources is to use the tests as a way to validate that your changes work. The tests are fairly robust and should help identify if any changes break the various use-cases that this repo handles.
