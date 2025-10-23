@echo off
setlocal enabledelayedexpansion
SET ALLUSERS=%1
{% for name in cookiecutter.install_options -%}
{%- set argn = loop.index + 1 -%}
SET OPTION_{{ name.upper() }}=%{{ argn }}
{% endfor -%}

CALL "%~dp0post_install.bat"
