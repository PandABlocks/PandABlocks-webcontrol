"""Requests and Responses, including the wire format the browser parses.

The expected dicts below used to be read from docs/reference/json/, which the
docs restructure removed - the tests had been failing on the missing files ever
since. They are the same examples, taken from pymalcolm upstream
(DiamondLightSource/pymalcolm, docs/reference/json), inlined so that the
serialized shapes stay covered without depending on files outside the tests.
"""

import unittest
from unittest.mock import ANY, MagicMock

from malcolm.compat import OrderedDict
from malcolm.core.request import Get, Post, Put, Request, Subscribe, Unsubscribe
from malcolm.core.response import Delta, Error, Response, Return, Update


class TestRequest(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.o = Request(32)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.id == 32
        assert self.o.callback == self.callback

    def test_respond_with_return(self):
        cb, response = self.o.return_response(value=5)
        assert cb == self.callback
        assert response.to_dict() == Return(id=32, value=5).to_dict()

    def test_respond_with_error(self):
        cb, response = self.o.error_response(exception=ValueError("Test Error"))
        assert cb == self.callback
        assert response.to_dict() == Error(id=32, message=ANY).to_dict()
        assert str(response.message) == "Test Error"

    def test_setters(self):
        self.o.set_callback(MagicMock())
        self.o.callback(888)
        self.callback.assert_not_called()


class TestGet(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.path = ["BL18I:XSPRESS3", "state", "value"]
        self.o = Get(32, self.path)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.typeid == "malcolm:core/Get:1.0"
        assert self.o.id == 32
        assert self.o.callback == self.callback
        assert self.path == self.o.path

    def test_setters(self):
        self.o.path = ["BL18I:XSPRESS3"]
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Get:1.0",
            "id": 32,
            "path": ["BL18I:XSPRESS3"],
        }

    def test_doc_state(self):
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Get:1.0",
            "id": 32,
            "path": ["BL18I:XSPRESS3", "state", "value"],
        }


class TestPut(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.path = ["BL18I:XSPRESS3:HDF", "filePath", "value"]
        self.value = "/path/to/file.h5"
        self.o = Put(35, self.path, self.value)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.typeid == "malcolm:core/Put:1.0"
        assert self.o.id == 35
        assert self.o.callback == self.callback
        assert self.path == self.o.path
        assert self.value == self.o.value

    def test_doc(self):
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Put:1.0",
            "id": 35,
            "path": ["BL18I:XSPRESS3:HDF", "filePath", "value"],
            "value": "/path/to/file.h5",
            "get": False,
        }


class TestPost(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.path = ["BL18I:XSPRESS3", "configure"]
        self.parameters = OrderedDict()
        self.parameters["filePath"] = "/path/to/file.h5"
        self.parameters["exposure"] = 0.1
        self.o = Post(2, self.path, self.parameters)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.typeid == "malcolm:core/Post:1.0"
        assert self.o.id == 2
        assert self.o.callback == self.callback
        assert self.path == self.o.path
        assert self.parameters == self.o.parameters

    def test_doc(self):
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Post:1.0",
            "id": 2,
            "path": ["BL18I:XSPRESS3", "configure"],
            "parameters": {"filePath": "/path/to/file.h5", "exposure": 0.1},
        }


class TestSubscribe(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.path = ["BL18I:XSPRESS3"]
        self.delta = True
        self.o = Subscribe(11, self.path, self.delta)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.typeid == "malcolm:core/Subscribe:1.0"
        assert self.o.id == 11
        assert self.o.callback == self.callback
        assert self.path == self.o.path
        assert self.delta == self.o.delta

    def test_respond_with_update(self):
        cb, response = self.o.update_response(value=5)
        assert cb == self.callback
        assert response.to_dict() == Update(id=11, value=5).to_dict()

    def test_respond_with_delta(self):
        changes = [[["path"], "value"]]
        cb, response = self.o.delta_response(changes)
        assert cb == self.callback
        assert response.to_dict() == Delta(id=11, changes=changes).to_dict()

    def test_setters(self):
        self.o.path = ["BL18I:XSPRESS3", "state", "value"]
        self.o.id = 19
        # The docs example left "delta" out, being the default; assert it
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Subscribe:1.0",
            "id": 19,
            "path": ["BL18I:XSPRESS3", "state", "value"],
            "delta": True,
        }

    def test_doc(self):
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Subscribe:1.0",
            "id": 11,
            "path": ["BL18I:XSPRESS3"],
            "delta": True,
        }


class TestUnsubscribe(unittest.TestCase):
    def setUp(self):
        self.callback = MagicMock()
        self.subscribe = Subscribe(32, ["."])
        self.subscribe.set_callback(self.callback)
        self.subscribes = {self.subscribe.generate_key(): self.subscribe}
        self.o = Unsubscribe(32)
        self.o.set_callback(self.callback)

    def test_init(self):
        assert self.o.typeid == "malcolm:core/Unsubscribe:1.0"
        assert self.o.id == 32

    def test_keys_same(self):
        assert self.subscribes[self.o.generate_key()] == self.subscribe

    def test_doc(self):
        assert self.o.to_dict() == {
            "typeid": "malcolm:core/Unsubscribe:1.0",
            "id": 32,
        }


class TestResponse(unittest.TestCase):
    def test_init(self):
        r = Response(123)
        assert r.id == 123

    def test_Return(self):
        r = Return(35)
        assert r.typeid == "malcolm:core/Return:1.0"
        assert r.id == 35
        assert r.value is None
        assert r.to_dict() == {
            "typeid": "malcolm:core/Return:1.0",
            "id": 35,
            "value": None,
        }

    def test_Return_value(self):
        r = Return(32, "Running")
        assert r.typeid == "malcolm:core/Return:1.0"
        assert r.id == 32
        assert r.value == "Running"
        assert r.to_dict() == {
            "typeid": "malcolm:core/Return:1.0",
            "id": 32,
            "value": "Running",
        }

    def test_Error(self):
        r = Error(2, "Non-existant block 'foo'")
        assert r.typeid == "malcolm:core/Error:1.0"
        assert r.id == 2
        assert r.message == "Non-existant block 'foo'"
        assert r.to_dict() == {
            "typeid": "malcolm:core/Error:1.0",
            "id": 2,
            "message": "Non-existant block 'foo'",
        }

    def test_Update(self):
        r = Update(19, "Running")
        assert r.typeid == "malcolm:core/Update:1.0"
        assert r.id == 19
        assert r.value == "Running"
        assert r.to_dict() == {
            "typeid": "malcolm:core/Update:1.0",
            "id": 19,
            "value": "Running",
        }

    def test_Delta(self):
        changes = [[["state", "value"], "Running"]]
        r = Delta(123, changes)
        assert r.typeid == "malcolm:core/Delta:1.0"
        assert r.id == 123
        assert r.changes == changes
