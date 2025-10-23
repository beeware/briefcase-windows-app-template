@echo off
setlocal enabledelayedexpansion
SET ALLUSERS=%1
{% for name in cookiecutter.install_options -%}
{%- set argn = loop.index + 1 -%}
SET {{ name.upper() }}=%{{ argn }}
{% endfor -%}

CALL "%~dp0post_install.bat"

echo ALLUSER=%ALLUSERS%
{% for name in cookiecutter.install_options -%}
echo {{ name }}=%{{ name.upper() }}%
{% endfor -%}
