# Dependabot に新しい版を見つけさせるためのファイル。このイメージは組み立てない。
# Dependabot は、pyproject.toml の requires-python などを書き換えられない。
# 書き換えられるのは FROM なので、ここを上げさせ、automation/versions.py が正本へ写す。
# イメージは Docker Hub のものに限る。待機（cooldown）が Docker Hub にしか効かないため。
FROM python:3.13.16-slim AS python
FROM astral/uv:0.13.5 AS uv
FROM node:24.20.0-slim AS node
FROM hashicorp/terraform:1.16.5 AS terraform
