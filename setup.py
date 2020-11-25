import setuptools

setuptools.setup(
    name='transform',
    version='0.1.0',
    description='Raster and vector files transformation service',
    author='Pantelis Mitropoulos',
    author_email='pmitropoulos@getmap.gr',
    license='MIT',
    packages=setuptools.find_packages(exclude=('tests*',)),
    install_requires=[
        # moved to requirements.txt
    ],
    package_data={'transform': [
        'logging.conf', 'schema.sql'
    ]},
    python_requires='>=3.7',
    zip_safe=False,
)
