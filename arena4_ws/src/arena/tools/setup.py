from setuptools import find_packages, setup

package_name = 'arena_tools'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=[
        'setuptools',
        'lxml',
        'arena_simulation_setup'
    ],
    zip_safe=True,
    maintainer='voshch',
    maintainer_email='dev@voshch.dev',
    description='TODO: Package description',
    license='MIT',
    # tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'zones_editor = arena_tools.ZonesEditor.__main__:main',
            'scenario_editor = arena_tools.ScenarioEditor.__main__:main'
        ],
    },
)
