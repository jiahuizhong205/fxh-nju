"""Literal query fixtures shared by API and real-extraction privacy tests."""

REJECTED_QUERY_URLS = tuple(f"https://example.com/course?{query}" for query in (
    "token%3Dhunter2",
    "password%3Dhunter2",
    "access_token%3Dshortsecret",
    "%74%6f%6b%65%6e%3Dhunter2",
    "page=2&token%3Dhunter2&lang=en",
    "page%3D2%26password%3Dhunter2%26lang%3Den",
    "%74%6f%6b%65%6e=hunter2",
    "token=%68%75%6e%74%65%72%32",
    "access+token%3Dshortsecret",
    "value=bearer+shortsecret",
    "value=%73%6b%2Dshortsecret",
    "value=Q7vN4+cM9-Lp2Xr8Bz5Kf3Ht6Wy1Ds0A",
    "%73%6b%2Dshortsecret=course",
    "%73%6b%2Dshortsecret",
    "topic=%FF",
    "topic=%E0%A4",
    "topic=%GG",
    "topic=%",
))

SAFE_QUERY_URLS = (
    "https://token.example.com/token-economics/?q=data%20science&lang=zh%2DCN",
    "https://example.com/course?%74opic%3Ddata+science%26page%3D2",
    "https://example.com/course?q=%E6%95%B0%E6%8D%AE&level=beginner",
    "https://example.com/course?discount=50%25&topic=token-economics",
)
