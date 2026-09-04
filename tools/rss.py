#!/usr/bin/env python3
"""Le um feed RSS. Uso: rss.py <url> [n]"""
import sys, feedparser
d=feedparser.parse(sys.argv[1])
n=int(sys.argv[2]) if len(sys.argv)>2 else 5
for e in d.entries[:n]:
    print(f"- {e.get('title','')}\n  {e.get('link','')}")
