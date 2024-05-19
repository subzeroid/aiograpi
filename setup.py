from setuptools import find_packages, setup

long_description = """
Asynchronous Instagram Private API wrapper.

Use the most recent version of the API from Instagram.

Features:

1. Performs Public API (web, anonymous) or Private API (mobile app, authorized)
   requests depending on the situation (to avoid Instagram limits)
2. Challenge Resolver have Email (as well as recipes for automating receive a code from email) and SMS handlers
3. Support upload a Photo, Video, IGTV, Clips (Reels), Albums and Stories
4. Support work with User, Media, Insights, Collections, Location (Place), Hashtag and Direct objects
5. Like, Follow, Edit account (Bio) and much more else
6. Insights by account, posts and stories
7. Build stories with custom background, font animation, swipe up link and mention users
"""

requirements = [
    "httpx==0.27.0",
    "orjson==3.10.3",
    "pydantic==2.7.1",
    "moviepy==1.0.3",
    "pycryptodomex==3.20.0",
    "zstandard==0.22.0",
]

setup(
    name="aiograpi",
    version="0.0.3",
    author="Mr.Robot",
    author_email="mr.robot@example.org",
    license="MIT",
    url="https://github.com/subzeroid/aiograpi",
    install_requires=requirements,
    keywords=[
        "instagram private api",
        "instagram-private-api",
        "instagram api",
        "instagram-api",
        "instagram",
        "instagram-scraper",
        "instagram-client",
        "instagram-stories",
        "instagram-feed",
        "instagram-reels",
        "instagram-insights",
        "downloader",
        "uploader",
        "videos",
        "photos",
        "albums",
        "igtv",
        "reels",
        "stories",
        "pictures",
        "instagram-user-photos",
        "instagram-photos",
        "instagram-metadata",
        "instagram-downloader",
        "instagram-uploader",
        "instagram-note",
    ],
    description="Asynchronous Instagram Private API wrapper",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.10",
    include_package_data=True,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
