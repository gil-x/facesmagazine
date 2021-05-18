import os
import sys
import sass
from css_html_js_minify import css_minifier

FILENAME = "main"

css_file = open( f"../css/{FILENAME}.css", "w", encoding="utf-8")
default_stdout = sys.stdout
sys.stdout = css_file

with open(f"{FILENAME}.scss", "r") as scss_file:
    print(str(sass.compile(string=scss_file.read())))
    sys.stdout = default_stdout

print(f"{FILENAME}.scss compilated to {FILENAME}.css")

min_css_file = open( f"../css/{FILENAME}.min.css", "w", encoding="utf-8")
default_stdout = sys.stdout
sys.stdout = min_css_file

with open(f"../css/{FILENAME}.css", "r") as css_file:
    print(css_minifier.css_minify(css_file.read()))
    sys.stdout = default_stdout

print(f"{FILENAME}.css minimized to {FILENAME}.min.css")
