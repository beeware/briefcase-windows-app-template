@echo off
setlocal enabledelayedexpansion
SET INSTALLER_UNATTENDED=%1
{% for name in cookiecutter.uninstall_options -%}
{%- set argn = loop.index + 1 -%}
SET OPTION_{{ name.upper() }}=%{{ argn }}
{% endfor -%}

CALL "%~dp0pre_uninstall.bat"
