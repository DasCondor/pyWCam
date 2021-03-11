from setuptools import setup

setup(
    name="pyWCam",
    packages=["pyWCam"],
    version="0.1.1",
    description="A library for simple OCR in Python using OpenCV",
    author="DasCondor & Alfren",
    url="https://github.com/DasCondor/pyWCam",
    download_url="https://github.com/DasCondor/pyWCam.git",
    keywords=["OCR", "OpenCV","Flask","WebCam","IPCam"],
    license="AGPL",
    classifiers=["Programming Language :: Python :: 3",
                 "License :: OSI Approved :: GNU Affero General Public License v2 or later (AGPLv2+)"],
    include_package_data=True,
    package_data={"": ["/templates/*.html"]},
    install_requires=["Flask", "opencv-python", "textwrap","argparse"]
)