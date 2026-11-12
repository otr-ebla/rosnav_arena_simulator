import os
from setuptools import setup, find_namespace_packages

package_name = 'arena_simulation_setup'


setup(
    name=package_name,
    version='1.0.0',
    packages=find_namespace_packages(
        where='.',
        include=[f'{package_name}*']
    ),
    package_dir={'': '.'},
    data_files=[
        ('share/' + package_name, ['package.xml']),
        # Will recursively track all .yaml files in the entities/robots
        # directory and its subdirectories.
        *[
            (
                os.path.join('share', package_name, base),
                [os.path.join(base, file)]
            )
            for dir in ['configs', 'entities', 'launch', 'resource', 'worlds', 'gazebo_models', 'common']
            for base, dirs, files in os.walk(dir)
            for file in files
        ],
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ],
    install_requires=[
        'setuptools',
        'requests',
        'attrs',
        'shapely',
        'pillow',
    ],
    zip_safe=True,
    maintainer='voshch',
    maintainer_email='dev@voshch.dev',
    description='arena_simulation_setup.',
    license='BSD',
    tests_require=['pytest'],
    scripts=[
        'scripts/model_staging',
    ],
    entry_points={
        'console_scripts': [
            'generate_world = arena_simulation_setup.utils.generative.world_generator:main',
            'world_generator = arena_simulation_setup.utils.generative.world_generator_ros:main',
            'model_staging = arena_simulation_setup.model_staging:main'
        ],
    },
)
