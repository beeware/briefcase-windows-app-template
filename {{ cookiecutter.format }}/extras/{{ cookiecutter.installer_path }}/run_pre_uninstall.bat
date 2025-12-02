@echo off
setlocal enabledelayedexpansion
{% for name in cookiecutter.uninstall_options -%}
SET OPTION_{{ name.upper() }}=%{{ loop.index }}
{% endfor -%}

CALL "%~dp0pre_uninstall.bat"
