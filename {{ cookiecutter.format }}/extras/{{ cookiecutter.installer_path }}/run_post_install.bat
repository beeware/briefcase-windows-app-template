@echo off
setlocal enabledelayedexpansion
SET ALLUSERS=%1
SET INSTALLER_PATH=%2
{% for name in cookiecutter.install_options -%}
{%- set argn = loop.index + 2 -%}
SET OPTION_{{ name.upper() }}=%{{ argn }}
{% endfor -%}

CALL "%~dp0post_install.bat"
