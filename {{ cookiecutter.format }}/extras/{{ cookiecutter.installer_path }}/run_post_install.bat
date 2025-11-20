@echo off
setlocal enabledelayedexpansion
FOR %%D IN ("%~dp0..") DO SET "INSTALLDIR=%%~fD"
SET ALLUSERS=%1
{% for name in cookiecutter.install_options -%}
{%- set argn = loop.index + 1 -%}
SET OPTION_{{ name.upper() }}=%{{ argn }}
{% endfor -%}

CALL "%~dp0post_install.bat"
