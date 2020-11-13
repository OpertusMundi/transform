import setuptools

setuptools.setup(
    name='transform',
    version='0.1',
    description='Raster and vector files transformation service',
    author='Pantelis Mitropoulos',
    author_email='pmitropoulos@getmap.gr',
    license='MIT',
    packages=setuptools.find_packages(),
    install_requires=[
        'gdal>=3.1.0,<3.2.0',
        'numpy>=1.18.4,<1.18.5',
        'pyproj>=2.6.0,<2.7.0',
        'Flask>=1.1.2,<1.1.3',
        'flask-executor>=0.9.3,<0.9.4',
        'apispec>=4.0.0,<4.1.0',
        'apispec-webframeworks>=0.5.2,<0.5.3',
        'flask-cors>=3.0.9,<3.1.0'
    ],
    package_data={'transform': ['logging.conf']},
    python_requires='>=3.7',
    zip_safe=False,
)