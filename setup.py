from setuptools import find_packages, setup

package_name = 'triggerbox_ros2'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='spencelab',
    maintainer_email='aspence@temple.edu',
    description='Defined timestamp trigger pulse host and firmware code.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'triggerbox_host = triggerbox_ros2.triggerbox_host:main'
            # will add client here when we update it's main func
            # to contain all in the old nodes/triggerbox_client.py...
        ],
    },
)
