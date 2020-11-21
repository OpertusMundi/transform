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
        # moved to requirements.txt
    ],
    package_data={'transform': ['logging.conf']},
    python_requires='>=3.7',
    zip_safe=False,
)
