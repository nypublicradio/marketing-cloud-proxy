FROM python:3.7

WORKDIR ~/marketing-cloud-proxy

# ADD setup.py setup.py

# RUN python -m pip install -U git+https://github.com/nypublicradio/nyprsetuptools.git
# RUN python -m pip install -e .

ADD . .

RUN python -m venv ~/.venv
RUN . ~/.venv/bin/activate
RUN python -m pip install -U git+https://github.com/nypublicradio/nyprsetuptools.git
RUN pip install -e .
RUN python setup.py test_requirements
