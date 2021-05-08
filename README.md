# sanic-motor
Simple motor wrapper for Sanic.

```
Notice:
version 0.5 requires Sanic >= 21.3

Works on Sanic >= 0.4.0 and MOTOR_URI need to be defined in app.config
```

## Installation

`pip install sanic-motor`

## Usage

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sanic import Sanic
from sanic.response import json
from sanic_jinja2 import SanicJinja2

from sanic_motor import BaseModel

app = Sanic(__name__)

settings = dict(
    MOTOR_URI='mongodb://localhost:27017/myapp', LOGO=None
)
app.config.update(settings)

BaseModel.init_app(app)
jinja = SanicJinja2(app, autoescape=True)


class User(BaseModel):
    __coll__ = 'users'
    __unique_fields__ = ['name']
    # __unique_fields__ = ['name, age']   # name and age for unique


@app.route('/')
async def index(request):
    cur = await User.find(sort='name')
    return jinja.render('index.html', request, users=cur.objects)


@app.route("/show/<id>")
async def show(request, id):
    # add as_raw = True to get the dict format record
    user_dict = await User.find_one(id, as_raw=True)

    # user = await User.find_one(id)
    return json(dict(user=user_dict))


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)

```
see examples and source code for details.

Run example:

    $cd example
    $virtualenv venv
    $. venv/bin/activate
    $pip install -r requirements.txt
    $python myapp.py

Open <http://localhost:8000> to see the example page.

![example](/example/example.png "example")
