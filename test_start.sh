#!/usr/bin/env bash
HERE="$(dirname "$(readlink -fn "$0")")"

PROD=/dls_sw/prod/common/python/RHEL6-x86_64
TOOLS=/dls_sw/prod/tools/RHEL6-x86_64
SITE_PACKAGES=lib/python2.7/site-packages

COTHREAD=(${PROD}/cothread/2-14/prefix/${SITE_PACKAGES}/*.egg)
NUMPY=(${TOOLS}/numpy/1-11-1/prefix/${SITE_PACKAGES}/*.egg)
ENUM=(${TOOLS}/enum34/1-0-4/prefix/${SITE_PACKAGES}/enum)
TORNADO=(${TOOLS}/tornado/4-3/prefix/${SITE_PACKAGES}/*.egg)
SD=(${TOOLS}/singledispatch/3-4-0-3/prefix/${SITE_PACKAGES}/*.egg)
ABC=(${TOOLS}/backports_abc/0-4/prefix/${SITE_PACKAGES}/*.egg)
CERTIFI=(${TOOLS}/certifi/2015-11-20/prefix/${SITE_PACKAGES}/*.egg)
SSL=(${TOOLS}/backports.ssl_match_hostname/3-4-0-2/prefix/${SITE_PACKAGES}/*.egg)

export PYTHONPATH=${HERE}/build:$COTHREAD:$NUMPY:$TORNADO:$SD:$ABC:$CERTIFI:$SSL:$ENUM

dls-python ${HERE}/src/panda-webcontrol.py --hostname=localhost \
    --templatedir=${HERE}/build/templates --etcdir=${HERE}/etc \
    --admindir=${HERE}/../PandABlocks-rootfs/rootfs/web-admin \
    --configdir=/tmp
