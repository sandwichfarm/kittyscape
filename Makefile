.PHONY: check unit installation artifact

check:
	python scripts/check.py
	python -m unittest discover -s tests/unit
	python -m unittest discover -s tests/installation

unit:
	python -m unittest discover -s tests/unit

installation:
	python -m unittest discover -s tests/installation

artifact:
	python scripts/build_release.py
