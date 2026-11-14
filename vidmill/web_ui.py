"""Embedded studio UI for `vmill serve`.

The page is dependency-free: plain HTML, CSS and JavaScript served from
one stdlib HTTP server. Layout follows a professional NLE — media bin and
project inspector on the left, program monitor with timeline in the centre,
the AI editor on the right. The parts live in three small modules so the
UI stays readable.
"""

from .web_ui_body import BODY
from .web_ui_css import CSS
from .web_ui_js import SCRIPT_A
from .web_ui_js2 import SCRIPT_B

HTML = (
    "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
    "<meta name=\"color-scheme\" content=\"dark\">\n"
    "<title>vidmill — studio</title>\n"
    "<link rel=\"icon\" href=\"data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='14' fill='%235b8cff'/%3E"
    "%3Cpath d='M25 18l22 14-22 14z' fill='white'/%3E%3C/svg%3E\">\n"
    "<style>" + CSS + "</style></head><body>\n"
    + BODY +
    "\n<script>" + SCRIPT_A + SCRIPT_B + "</script></body></html>\n"
)
