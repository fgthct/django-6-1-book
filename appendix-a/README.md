# upgrade-lab

A tiny Django project (one model, SQLite) and a program, `probe.py`, that runs one probe
for each feature that changes between Django 5.2, 6.0 and 6.1. Used in Appendix A.

    for v in 5.2 6.0 6.1; do
      uv venv --python 3.14 venv_$v && uv pip install --python venv_$v/bin/python "django>=$v,<${v%.*}.$((${v#*.}+1))"
      venv_$v/bin/python probe.py
    done

`DEFAULT_AUTO_FIELD` is deliberately not set (the "old project" case of A.4).
