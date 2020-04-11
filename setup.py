from setuptools import setup, find_packages
import btclib

with open('README.md', 'r') as fh:
    longdescription = fh.read()

setup(
    name = btclib.name,
    version = btclib.__version__,
    license = btclib.__license__,
    author = btclib.__author__,
    long_description = longdescription,
    long_description_content_type = 'text/markdown',
    packages = find_packages(),
    include_package_data = True,
)
