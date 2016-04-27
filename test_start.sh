cd $(dirname $0)/build/webserver
PYTHONPATH=../lib/python2.7/site-packages:/dls_sw/prod/tools/RHEL6-x86_64/numpy/1-7-0/prefix/lib/python2.7/site-packages/numpy-1.7.0-py2.7-linux-x86_64.egg:/dls_sw/prod/common/python/RHEL6-x86_64/cothread/2-13/prefix/lib/python2.7/site-packages/cothread-2.13-py2.7-linux-x86_64.egg:/dls_sw/work/tools/RHEL6-x86_64/ws4py/prefix/lib/python2.7/site-packages/ws4py-0.3.4-py2.7.egg dls-python zebra2-webserver.py --port=8080


