#!/bin/bash

cd "$(dirname "$0")"

if [[ ! -d "bookcollection-env" ]]; then
	python3 -m venv bookcollection-env
fi

source bookcollection-env/bin/activate

if [[ -f "requirements.txt" ]]; then
	pip install -r requirements.txt
fi

python app.py
