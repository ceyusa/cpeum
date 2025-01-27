#!/bin/sh -ex

if [ -d venv ]
then
    python3 -m venv --upgrade venv
    . venv/bin/activate
    pip install --upgrade pip
    pip install --upgrade -r requirements.txt
    pre-commit autoupdate
else
    python -m venv venv
    . venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pre-commit install
fi
