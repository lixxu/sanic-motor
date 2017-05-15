#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sanic import Sanic
from sanic.response import text
from sanic_motor import BaseModel

app = Sanic()

settings = dict(MOTOR_URI='mongodb://localhost:27017/myapp',
                LOGO=None,
                )
app.config.update(settings)

BaseModel.init_app(app)


class User(BaseModel):
    __coll__ = 'users'


@app.route('/')
async def index(request):
    doc = await User.find_one()
    return text('index' + (doc.name if doc else 'no user'))


def test_index():
    request, response = app.test_client.get('/')
    assert response.status == 200


def test_index_again():
    request, response = app.test_client.get('/')
    assert response.status == 200


if __name__ == '__main__':
    test_index()
    test_index_again()
