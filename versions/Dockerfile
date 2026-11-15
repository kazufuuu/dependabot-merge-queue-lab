# バージョンを管理する場所ではない。バージョンを確かめるとき、変えるときは、ここではなく管理場所を見る。
# 管理場所は、.python-version（Python）、.node-version（Node）、infra/versions.tf（Terraform）。
# 管理場所を書き換えたあと、uv run just align を動かすと、このファイルが揃う。
#
# Dependabot に新しいバージョンを見つけさせるためのファイル。このイメージはビルドしない。
# Dependabot は、.python-version などの管理場所を書き換えられない。
# 書き換えられるのは FROM なので、ここを上げさせ、.github/scripts/versions.py が .python-version などへ写す。
# イメージは Docker Hub のものに限る。cooldown が Docker Hub にしか効かないため。
# FROM の間には行を挟む。隣り合う行を別々の PR が変えると、片方が入ったあとに、もう片方が衝突する。

# Python（管理場所は .python-version）
FROM python:3.13.16-slim AS python

# Node（管理場所は .node-version）
FROM node:24.20.0-slim AS node

# Terraform（管理場所は infra/versions.tf）
FROM hashicorp/terraform:1.16.5 AS terraform
