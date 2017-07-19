"""
sanic-motor
--------------
Simple Motor wrapper for sanic
"""
from setuptools import setup

setup(
    name='sanic-motor',
    version='0.2.4',
    url='https://github.com/lixxu/sanic-motor',
    license='BSD',
    author='Lix Xu',
    author_email='xuzenglin@gmail.com',
    description='Simple Motor wrapper for sanic',
    long_description=__doc__,
    packages=['sanic_motor'],
    zip_safe=False,
    platforms='any',
    install_requires=['motor>=1.0', 'sanic>=0.4.0'],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)
