"""Setup script for footy-predictor CLI."""

from setuptools import setup, find_packages

setup(
    name="footy-predictor",
    version="1.0.0",
    description="Football Match Analysis CLI Tool",
    author="Footy Predictor Team",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "typer==0.9.0",
        "httpx==0.27.0",
        "rich==13.7.1",
        "pandas==2.2.2",
        "python-dotenv==1.0.1",
        "pydantic-settings==2.4.0",
    ],
    entry_points={
        "console_scripts": [
            "matchday=cli.main:app",
            "footy-predictor=cli.main:app",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
