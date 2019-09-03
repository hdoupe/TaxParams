import setuptools
import os

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="taxparams",
    version=os.environ.get("VERSION", "0.0.0"),
    author="Hank Doupe",
    author_email="henrymdoupe@gmail.com",
    description=(
        "Tax-Calculator compatible ParamTools class"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hdoupe/TaxParams",
    packages=setuptools.find_packages(),
    install_requires=["paramtools"],
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
