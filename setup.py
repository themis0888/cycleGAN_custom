#nsml: nsml/default_ml:latest

from distutils.core import setup
setup(
        name='nsml example 10 ladder_network',
        version='1.0',
        description='ns-ml',
        install_requires=[
            'matplotlib',
            'tqdm',
            'pillow',
            'scipy',
            'numpy',
            'imageio'
        ]
)
