"""Setup file for persona-agent."""

from setuptools import find_packages, setup

setup(
    name="persona-agent",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
)
