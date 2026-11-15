# Dependabot に新しい版を見つけさせるためのファイル。このイメージは組み立てない。
# Dependabot は、.python-version などの正本を書き換えられない。
# 書き換えられるのは FROM なので、ここを上げさせ、automation/versions.py が正本へ写す。
# イメージは Docker Hub のものに限る。待機（cooldown）が Docker Hub にしか効かないため。
# FROM の間には行を挟む。隣り合う行を別々の PR が変えると、片方が入ったあとに、もう片方が衝突する。

# Python（正本は .python-version）
FROM python:3.13.16-slim AS python

# Node（正本は .tool-versions）
FROM node:24.20.0-slim AS node

# Terraform（正本は infra/versions.tf）
FROM hashicorp/terraform:1.16.5 AS terraform
