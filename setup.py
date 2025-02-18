from setuptools import find_packages
from setuptools import setup

setup(
    name="citus-cloud-mgmt",
    description="Tools to manage some Citus Cloud entities",
    long_description=open("README.md").read(),  # no "with..." will do for setup.py
    long_description_content_type="text/markdown; charset=UTF-8; variant=GFM",
    license="MIT",
    author="Kyrylo Shpytsya",
    author_email="kyrylo.shpytsya@prism.ai",
    url="https://github.com/prismai/citus-cloud-mgmt",
    install_requires=[
        "atomicwrites>=1.4.0,<2",
        "beautifulsoup4>=4.9.1,<5",
        "click>=7.1.2,<8",
        "click-log>=0.3.2,<1",
        "psycopg2>=2.8.5,<3",
        "pynacl>=1.4.0,<2",
        "pyotp>=2.3.0,<3",
        "requests>=2.24.0,<3",
        "tabulate>=0.8.7,<1",
    ],
    setup_requires=["setuptools_scm"],
    use_scm_version=True,
    python_requires=">=3.7, <3.10",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    zip_safe=False,
    entry_points={
        "console_scripts": ["citus-cloud-mgmt = citus_cloud_mgmt._cli:main"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: BSD :: FreeBSD",
        "Operating System :: POSIX :: BSD :: OpenBSD",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: System :: Systems Administration",
    ],
)
