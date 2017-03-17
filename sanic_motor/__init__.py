#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    specs = [{k: v} for k, v in doc.items() if k in fields]
    return {'$or': specs} if specs else None


class BaseModel:
    __coll__ = None
    __collection__ = None
    __unique_fields__ = []
    __motor_client__ = None
    __motor_db__ = None
    __app__ = None

    def __init__(self, *args, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def init_app(cls, app, open_listener='before_server_start',
                 close_listener='before_server_stop'):
        BaseModel.__app__ = app

        if open_listener:
            @app.listener(open_listener)
            async def open_connection(app, loop):
                connect = app.config.get('MOTOR_CONNECT', True)
                client = AsyncIOMotorClient(app.config.MOTOR_URI,
                                            connect=connect)
                db = client.get_default_database()
                app.motor_client = client
                BaseModel.__motor_client__ = client
                BaseModel.__motor_db__ = db

        if close_listener:
            @app.listener(close_listener)
            async def close_connection(app, loop):
                app.motor_client.close()

    @property
    def id(self):
        return self['_id']

    @classmethod
    def get_id(cls, _id):
        if isinstance(_id, str):
            try:
                oid = ObjectId(_id)
                if str(oid) == _id:
                    return oid

            except:
                pass

        return _id

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
    def get_collection(cls):
        if not cls.__coll__:
            raise ValueError('collection name is required, cls.__coll__')

        if not cls.__collection__:
            cls.__collection__ = cls.__motor_db__[cls.__coll__]

        return cls.__collection__

    @classmethod
    async def is_unique(cls, fields=[], doc={}, id=None):
        spec = get_uniq_spec(fields or cls.__unique_fields__, doc)
        if spec:
            if id:
                spec['_id'] = {'$ne': id}

            return await cls.find_one(spec)

        return True

    @classmethod
    def get_page_args(cls, request, page_name='page',
                      per_page_name='per_page'):
        page = request.args.get(page_name, 1)
        per_page = request.args.get(per_page_name, 10)
        try:
            per_page = int(per_page)
        except:
            per_page = 10

        try:
            page = int(page)
        except:
            page = 1

        return page, per_page, per_page * (page - 1)

    @classmethod
    async def find(cls, request=None, *args, **kwargs):
        if request is not None:
            page_name = kwargs.pop('page_name', 'page')
            per_page_name = kwargs.pop('per_page_name', 'per_page')

            page, per_page, skip = cls.get_page_args(request, page_name,
                                                     per_page_name)
            kwargs.setdefault('limit', per_page)
            kwargs.setdefault('skip', skip)

        # convert to object or keep dict format
        as_raw = kwargs.pop('as_raw', False)
        do_async_for = kwargs.pop('do_async_for', True)  # async for result
        kwargs.update(sort=get_sort(kwargs.get('sort')))
        cur = cls.get_collection().find(*args, **kwargs)
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
        as_raw = kwargs.pop('as_raw', False)
        if isinstance(filter, (str, ObjectId)):
            filter = dict(_id=cls.get_id(filter))

        doc = await cls.get_collection().find_one(filter, *args, **kwargs)
        return (doc if as_raw else cls(**doc)) if doc else None

    @classmethod
    async def insert_one(cls, doc, **kwargs):
        return await cls.get_collection().insert_one(doc, **kwargs)

    @classmethod
    async def insert_many(cls, *args, **kwargs):
        return await cls.get_collection().insert_many(*args, **kwargs)

    @classmethod
    async def update_one(cls, *args, **kwargs):
        return await cls.get_collection().update_one(*args, **kwargs)

    @classmethod
    async def update_many(cls, *args, **kwargs):
        return await cls.get_collection().update_many(*args, **kwargs)

    @classmethod
    async def replace_one(cls, *args, **kwargs):
        return await cls.get_collection().replace_one(*args, **kwargs)

    @classmethod
    async def delete_one(cls, filter, **kwargs):
        return await cls.get_collection().delete_one(filter, **kwargs)

    @classmethod
    async def delete_many(cls, filter, **kwargs):
        return await cls.get_collection().delete_many(filter, **kwargs)

    async def destroy(self, **kwargs):
        return await self.__class__.delete_one({'_id': self.id}, **kwargs)

    @classmethod
    async def aggregate(cls, pipeline, **kwargs):
        docs = []
        async for doc in cls.get_collection().aggregate(pipeline, **kwargs):
            docs.append(doc)

        return docs

    @classmethod
    async def bulk_write(cls, requests, **kwargs):
        return await cls.get_collection().bulk_write(requests, **kwargs)

    @classmethod
    async def create_index(cls, keys, **kwargs):
        keys = get_sort(keys)
        coll = cls.get_collection()
        if keys and isinstance(keys, list):
            if isinstance(keys[0], list):  # [[(...), (...)], [(...)]]
                for key in keys:
                    await coll.create_index(key, **kwargs)

            else:  # [(), ()]
                await coll.create_index(keys, **kwargs)

    @classmethod
    async def create_indexes(cls, indexes):
        return await cls.get_collection().create_indexes(indexes)

    @classmethod
    async def count(cls, *args, **kwargs):
        return await cls.get_collection().count(*args, **kwargs)

    @classmethod
    async def distinct(cls, key, *args, **kwargs):
        return await cls.get_collection().distinct(key, *args, **kwargs)

    @classmethod
    async def drop_index(cls, index_or_name):
        return await cls.get_collection().drop_index(index_or_name)

    @classmethod
    async def drop_indexes(cls):
        return await cls.get_collection().drop_indexes()

    @classmethod
    async def find_one_and_delete(cls, *args, **kwargs):
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection().find_one_and_delete(*args, **kwargs)

    @classmethod
    async def find_one_and_replace(cls, *args, **kwargs):
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection().find_one_and_replace(*args, **kwargs)

    @classmethod
    async def find_one_and_update(cls, *args, **kwargs):
        kwargs.update(sort=get_sort(kwargs.pop('sort', None)))
        return await cls.get_collection().find_one_and_update(*args, **kwargs)

    @classmethod
    async def group(cls, *args, **kwargs):
        return await cls.get_collection().group(*args, **kwargs)

    @classmethod
    async def index_information(cls):
        return await cls.get_collection().index_information()

    @classmethod
    async def list_indexes(cls):
        return await cls.get_collection().list_indexes()

    @classmethod
    async def map_reduce(cls, *args, **kwargs):
        return await cls.get_collection().map_reduce(*args, **kwargs)

    @classmethod
    async def options(cls):
        return await cls.get_collection().options()

    @classmethod
    def parallel_scan(cls, *args, **kwargs):
        return cls.get_collection().parallel_scan(*args, **kwargs)

    @classmethod
    async def reindex(cls):
        return await cls.get_collection().reindex()

    @classmethod
    def with_options(cls, *args, **kwargs):
        return cls.get_collection().with_options(*args, **kwargs)

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
