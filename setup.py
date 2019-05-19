from setuptools import setup, find_packages

setup(
    name="ymcli",
    version="0.0.1",
    author='Borodin Gregory',
    author_email='grihabor@gmail.com',
    url='https://github.com/grihabor/ymcli',
    license='MIT',
    package_dir={'': 'src'},
    packages=find_packages('src'),
)
