from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = [line.strip() for line in f.readlines() if line.strip() and not line.startswith("#")]

from amp import __version__ as version

setup(
	name="amp",
	version=version,
	description="AMP - App for Managing Projects for ERPNext",
	author="PMG Team",
	author_email="info@example.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
