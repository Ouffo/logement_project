lint:
	ruff check . --fix
	ruff format .

test:
	pytest
