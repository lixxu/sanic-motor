#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sanic.log import log
from pymongo import (ASCENDING, DESCENDING, GEO2D, GEOHAYSTACK, GEOSPHERE,
                     HASHED, TEXT)
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

INDEX_NAMES = dict(asc=ASCENDING, ascending=ASCENDING,
                   desc=DESCENDING, descending=DESCENDING,
                   geo2d=GEO2D,
                   geohaystack=GEOHAYSTACK,
                   geosphere=GEOSPHERE,
                   hashed=HASHED,
                   text=TEXT,
                   )


def get_sort(sort):
    if sort is None or isinstance(sort, list):
        return sort

    sorts = []
    for items in sort.strip().split(';'):  # ; for many indexes
        items = items.strip()
        if items:
            lst = []
            for item in items.split(','):
                item = item.strip()
                if item:
                    if ' ' in item:
                        field, _sort = item.replace('  ', ' ').split(' ')[:2]
                        lst.append((field, INDEX_NAMES[_sort.lower()]))
                    else:
                        lst.append((item, ASCENDING))

            if lst:
                sorts.append(lst)

    return sorts[0] if len(sorts) == 1 else sorts


def get_uniq_spec(fields=[], doc={}):
    specs = []
    for field in fields:
        spec = {}
        for k in [f.strip() for f in field.split(',') if f.strip()]:
            if k in doc:
                spec[k] = doc[k]

        if spec:
            specs.append(spec)

    return {'$or': specs} if specs else None


class BaseModel:
    __coll__ = None  # collection name
    __dbkey__ = None  # which database connected to?
    __unique_fields__ = []
    __motor_client__ = None
    __motor_db__ = None
    __motor_clients__ = {}
    __motor_dbs__ = {}
    __app__ = None
    __apps__ = {}

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    @staticmethod
    def init_app(app, open_listener='before_server_start',
                 close_listener='before_server_stop', name=None, uri=None):
        BaseModel.__app__ = app
        BaseModel.__apps__[name or app.name] = app

        if open_listener:
            @app.listener(open_listener)
            async def open_connection(app, loop):
                BaseModel.default_open_connection(app, loop, name, uri)

        if close_listener:
            @app.listener(close_listener)
            async def close_connection(app, loop):
                BaseModel.default_close_connection(app, loop)

    @staticmethod
    def default_open_connection(app, loop, name=None, uri=None):
        if not name:
            name = app.name

        log.info('opening motor connection for [{}]'.format(name))
        client = AsyncIOMotorClient(uri or app.config.MOTOR_URI, io_loop=loop)
        db = client.get_default_database()
        app.motor_client = client
        BaseModel.__motor_client__ = client
        BaseModel.__motor_db__ = db
        if not hasattr(app, 'motor_clients'):
            app.motor_clients = {}

        app.motor_clients[name] = client
        BaseModel.__motor_clients__[name] = client
        BaseModel.__motor_dbs__[name] = db

    @staticmethod
    def default_close_connection(app, loop):
        if hasattr(app, 'motor_clients'):
            for name, client in app.motor_clients.items():
                log.info('closing motor connection for [{}]'.format(name))
                client.close()

    @property
    def id(self):
        return self['_id']

    @classmethod
    def get_oid(cls, _id):
        return ObjectId(_id) if ObjectId.is_valid(_id) else _id

    def __getitem__(self, key):
        return self.__dict__.get(key)

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __repr__(self):
        return '{}'.format(self.__dict__)

    def __getattr__(self, key):
        """just return None instead of key error"""
        return None

    @classmethod
    def get_collection(cls, db=None):
        if not cls.__coll__:
            raise ValueError('collection name is required, set __coll__')

        if not db:
            db = cls.__dbkey__ or cls.__app__.name

        return cls.__motor_dbs__[db][cls.__coll__]

    @classmethod
    async def is_unique(cls, fields=[], doc={}, id=None, *args, **kwargs):
        spec = get_uniq_spec(fields or cls.__unique_fields__, doc)
        if spec:
            if id:
                spec['_id'] = {'$ne': id}

            return await cls.find_one(spec, *args, **kwargs)

        return True

    @classmethod
    def get_page_args(cls, request=None, page_name='page',
                      per_page_name='per_page', **kwargs):
        page = kwargs.get(page_name)
        per_page = kwargs.get(per_page_name)
        if request:
            if not page:
                page = request.args.get(page_name, 1)

            if not per_page:
                per_page = request.args.get(per_page_name, 10)

        if not (page and per_page):
            return 0, 0, 0

        try:
            per_page = int(per_page)
        except (ValueError, TypeError):
            per_page = 10

        try:
            page = int(page)
        except (ValueError, TypeError):
            page = 1

        return page, per_page, per_page * (page - 1)

    @classmethod
    async def find(cls, request=None, *args, **kwargs):
        page_name = kwargs.pop('page_name', 'page')
        per_page_name = kwargs.pop('per_page_name', 'per_page')
        page, per_page, skip = cls.get_page_args(request, page_name,
                                                 per_page_name, **kwargs)
        if per_page:
            kwargs.setdefault('limit', per_page)

        if skip:
            kwargs.setdefault('skip', skip)

        kwargs.pop(page_name, None)
        kwargs.pop(per_page_name, None)

        # convert to object or keep dict format
        as_raw = kwargs.pop('as_raw', False)
        do_async_for = kwargs.pop('do_async_for', True)  # async for result
        kwargs.update(sort=get_sort(kwargs.get('sort')))

        db = kwargs.pop('db', None)
        cur = cls.get_collection(db).find(*args, **kwargs)
        objs = []
        if do_async_for:
            if as_raw:
                async for doc in cur:
                    objs.append(doc)

            else:
                async for doc in cur:
                    objs.append(cls(**doc))

        cur.objects = objs
        return cur

    @classmethod
    async def find_one(cls, filter=None, *args, **kwargs):
        db = kwargs.pop('db', None)
        as_raw = kwargs.pop('as_raw', False)
        if isinstance(filter, (str, ObjectId)):
            filter = dict(_id=cls.get_oid(filter))

        doc = await cls.get_collection(db).find_one(filter, *args, **kwargs)
        return (doc if as_raw else cls(**doc)) if doc else None

    @classmethod
    async def insert_one(cls, doc, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).insert_one(doc, **kwargs)

    @classmethod
    async def insert_many(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).insert_many(*args, **kwargs)

    @classmethod
    async def update_one(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).update_one(*args, **kwargs)

    @classmethod
    async def update_many(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).update_many(*args, **kwargs)

    @classmethod
    async def replace_one(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).replace_one(*args, **kwargs)

    @classmethod
    async def delete_one(cls, filter, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).delete_one(filter, **kwargs)

    @classmethod
    async def delete_many(cls, filter, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).delete_many(filter, **kwargs)

    async def destroy(self, **kwargs):
        return await self.__class__.delete_one({'_id': self.id}, **kwargs)

    @classmethod
    async def aggregate(cls, pipeline, **kwargs):
        db = kwargs.pop('db', None)
        docs = []
        async for doc in cls.get_collection(db).aggregate(pipeline, **kwargs):
            docs.append(doc)

        return docs

    @classmethod
    async def bulk_write(cls, requests, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).bulk_write(requests, **kwargs)

    @classmethod
    async def create_index(cls, keys, **kwargs):
        db = kwargs.pop('db', None)
        keys = get_sort(keys)
        coll = cls.get_collection(db)
        if keys and isinstance(keys, list):
            if isinstance(keys[0], list):  # [[(...), (...)], [(...)]]
                for key in keys:
                    await coll.create_index(key, **kwargs)

            else:  # [(), ()]
                await coll.create_index(keys, **kwargs)

    @classmethod
    async def create_indexes(cls, indexes, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).create_indexes(indexes)

    @classmethod
    async def count(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).count(*args, **kwargs)

    @classmethod
    async def distinct(cls, key, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).distinct(key, *args, **kwargs)

    @classmethod
    async def drop_index(cls, index_or_name, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).drop_index(index_or_name)

    @classmethod
    async def drop_indexes(cls, db=None):
        return await cls.get_collection(db).drop_indexes()

    @classmethod
    async def find_one_and_delete(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection(db).find_one_and_delete(*args,
                                                                **kwargs)

    @classmethod
    async def find_one_and_replace(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection(db).find_one_and_replace(*args,
                                                                 **kwargs)

    @classmethod
    async def find_one_and_update(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection(db).find_one_and_update(*args,
                                                                **kwargs)

    @classmethod
    async def group(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).group(*args, **kwargs)

    @classmethod
    async def index_information(cls, db=None):
        return await cls.get_collection(db).index_information()

    @classmethod
    async def list_indexes(cls, db=None):
        return await cls.get_collection(db).list_indexes()

    @classmethod
    async def map_reduce(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return await cls.get_collection(db).map_reduce(*args, **kwargs)

    @classmethod
    async def options(cls, db=None):
        return await cls.get_collection(db).options()

    @classmethod
    def parallel_scan(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return cls.get_collection(db).parallel_scan(*args, **kwargs)

    @classmethod
    async def reindex(cls, db=None):
        return await cls.get_collection(db).reindex()

    @classmethod
    def with_options(cls, *args, **kwargs):
        db = kwargs.pop('db', None)
        return cls.get_collection(db).with_options(*args, **kwargs)

    @classmethod
    def get_sort(cls, sort):
        return get_sort(sort)

    @classmethod
    def get_uniq_spec(cls, fields=[], doc={}):
        return get_uniq_spec(fields or cls.__unique_fields__, doc)

    def clean_for_dirty(self, doc={}, keys=[]):
        """Remove non-changed items."""
        dct = self.__dict__
        for k in (keys or doc.keys()):
            if k in doc and k in dct and doc[k] == dct[k]:
                doc.pop(k)
