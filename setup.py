import setuptools
from distutils.core import setup
import platform

import numpy as np

__version__ = '0.0.1dev'

mappy_name = 'GeoWombat'
maintainer = 'Jordan Graesser'
maintainer_email = ''
description = 'Geo-enabled n-dimensional arrays from satellite imagery'
git_url = 'http://github.com/jgrss/geowombat.git'

with open('README.md') as f:
    long_description = f.read()

with open('LICENSE.txt') as f:
    license_file = f.read()

MPGLUE_LINK = 'git+https://github.com/jgrss/mpglue.git@master#egg=mpglue-0'

required_packages = ['matplotlib',
                     'cartopy',
                     'GDAL',
                     'geopandas',
                     'numpy',
                     'rasterio']


def get_packages():
    return setuptools.find_packages()


def get_package_data():
    return {'': ['*.md', '*.txt']}


def setup_package():

    include_dirs = [np.get_include()]

    metadata = dict(name=mappy_name,
                    maintainer=maintainer,
                    maintainer_email=maintainer_email,
                    description=description,
                    license=license_file,
                    version=__version__,
                    long_description=long_description,
                    packages=get_packages(),
                    package_data=get_package_data(),
                    zip_safe=False,
                    download_url=git_url,
                    install_requires=required_packages,
                    dependency_links=[MPGLUE_LINK],
                    include_dirs=include_dirs)

    setup(**metadata)


if __name__ == '__main__':
    setup_package()