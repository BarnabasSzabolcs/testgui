rm -R build
rm -R dist
python3 -m pip install --upgrade build
python3 -m pip install --upgrade twine
python3 -m build
# https://packaging.python.org/guides/using-testpypi/
twine upload --repository testpypi dist/*