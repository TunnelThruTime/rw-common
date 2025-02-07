
from setuptools import setup

setup(
        name='rw',
        description='record demos with sox rec',
        version='0.0.1',
	data_files = [('/usr/local/share/man/man1', ['docs/man/rw.1/'])],
	long_description='rw is a cli for recording demos with sox',
        py_modules=['rwmain'],
	packages=['modules'],
        author='Laurence Allan Lawlor',
        author_email='',
        install_requires=[
            'rich',
            'pyaudio',
            'numpy',
            'keyboard',
            'urwid',
            'Click',
            'ipython',
	    'pretty_errors'],
        entry_points={
            'console_scripts': [
                'rw = rwmain:cli' ],
            },  
        )   

