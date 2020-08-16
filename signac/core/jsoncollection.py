# Copyright (c) 2020 The Regents of the University of Michigan
# All rights reserved.
# This software is licensed under the BSD 3-Clause License.
"""Implements JSON-backend.

This implements the JSON-backend for SyncedCollection API by
implementing sync and load methods.
"""
import os
import json
import errno
import uuid

from .synced_collection import SyncedCollection
from .buffered_collection import BufferedSyncedCollection
from .syncedattrdict import SyncedAttrDict
from .synced_list import SyncedList
from .buffered_collection import _store_in_buffer
from .buffered_collection import _get_filemetadata


class JSONCollection(BufferedSyncedCollection):
    """Implement sync and load using a JSON back end."""

    backend = __name__  # type: ignore

    def __init__(self, filename=None, data=None, write_concern=False, **kwargs):
        kwargs['data'] = data
        self._filename = None if filename is None else os.path.realpath(filename)
        super().__init__(**kwargs)
        if (filename is None) == (self._parent is None):
            raise ValueError(
                "Illegal argument combination, one of the two arguments, "
                "parent or filename must be None, but not both.")
        self._backend_kwargs['filename'] = self._filename
        self._backend_kwargs['write_concern'] = write_concern
        if data is not None:
            self.sync()

    def _load(self):
        """Load the data from a JSON-file."""
        try:
            with open(self._filename, 'rb') as file:
                blob = file.read()
                return json.loads(blob)
        except IOError as error:
            if error.errno == errno.ENOENT:
                return None

    def _sync(self, data=None):
        """Write the data to JSON-file."""
        if data is None:
            data = self.to_base()
        # Serialize data:
        blob = json.dumps(data).encode()
        # When write_concern flag is set, we write the data into dummy file and then
        # replace that file with original file.
        if self._backend_kwargs['write_concern']:
            dirname, filename = os.path.split(self._filename)
            fn_tmp = os.path.join(dirname, '._{uid}_{fn}'.format(
                uid=uuid.uuid4(), fn=filename))
            with open(fn_tmp, 'wb') as tmpfile:
                tmpfile.write(blob)
            os.replace(fn_tmp, self._filename)
        else:
            with open(self._filename, 'wb') as file:
                file.write(blob)

    def _write_to_cache(self, cache=None, data=None):
        data = self.to_base() if data is None else data
        cache = self._cache if cache is None else cache
        cache[self._filename] = json.dumps(data)

    def _read_from_cache(self, cache=None):
        cache = self._cache if cache is None else cache
        try:
            data = cache[self._filename]
        except KeyError:
            data = None
        return json.loads(data) if data is not None else None

    @staticmethod
    def _get_metadata(filename):
        return _get_filemetadata(filename)

    def _write_to_buffer(self):
        _store_in_buffer(self._filename, self._backend_kwargs, self.backend,
                         cache=self._cache, metadata=self._get_metadata(self._filename))

    @classmethod
    def _sync_from_buffer(cls, id, backend_kwargs, cache, metadata=None):
        # compare the metadata and
        if metadata is not None:
            if metadata != cls._get_metadata(id):
                return False  # if matadata do not match abandon the sync
        data = json.loads(cache[id])
        cls.from_base(data=data, **backend_kwargs)._sync()
        return True


class JSONDict(JSONCollection, SyncedAttrDict):
    """A dict-like mapping interface to a persistent JSON file.

    The JSONDict inherits from :class:`~core.collection_api.SyncedCollection`
    and :class:`~core.syncedattrdict.SyncedAttrDict`.

    .. code-block:: python

        doc = JSONDict('data.json', write_concern=True)
        doc['foo'] = "bar"
        assert doc.foo == doc['foo'] == "bar"
        assert 'foo' in doc
        del doc['foo']

    .. code-block:: python

        >>> doc['foo'] = dict(bar=True)
        >>> doc
        {'foo': {'bar': True}}
        >>> doc.foo.bar = False
        {'foo': {'bar': False}}

    .. warning::

        While the JSONDict object behaves like a dictionary, there are
        important distinctions to remember. In particular, because operations
        are reflected as changes to an underlying file, copying (even deep
        copying) a JSONDict instance may exhibit unexpected behavior. If a
        true copy is required, you should use the `to_base()` method to get a
        dictionary representation, and if necessary construct a new JSONDict
        instance: `new_dict = JSONDict(old_dict.to_base())`.

    Parameters
    ----------
    filename: str, optional
        The filename of the associated JSON file on disk (Default value = None).
    data: mapping, optional
        The intial data pass to JSONDict. Defaults to `list()`
    parent: object, optional
        A parent instance of JSONDict or None (Default value = None).
    write_concern: bool, optional
        Ensure file consistency by writing changes back to a temporary file
        first, before replacing the original file (Default value = None).
    """

    pass


class JSONList(JSONCollection, SyncedList):
    """A non-string sequence interface to a persistent JSON file.

    The JSONDict inherits from :class:`~core.collection_api.SyncedCollection`
    and :class:`~core.syncedlist.SyncedList`.

    .. code-block:: python

        synced_list = JSONList('data.json', write_concern=True)
        synced_list.append("bar")
        assert synced_list[0] == "bar"
        assert len(synced_list) == 1
        del synced_list[0]

    .. warning::

        While the JSONList object behaves like a list, there are
        important distinctions to remember. In particular, because operations
        are reflected as changes to an underlying file, copying (even deep
        copying) a JSONList instance may exhibit unexpected behavior. If a
        true copy is required, you should use the `to_base()` method to get a
        dictionary representation, and if necessary construct a new JSONList
        instance: `new_list = JSONList(old_list.to_base())`.

    Parameters
    ----------
    filename: str
        The filename of the associated JSON file on disk (Default value = None).
    data: non-str Sequence
        The intial data pass to JSONDict
    parent: object
        A parent instance of JSONDict or None (Default value = None).
    write_concern: bool
        Ensure file consistency by writing changes back to a temporary file
        first, before replacing the original file (Default value = None).
    """

    pass


SyncedCollection.register(JSONCollection, JSONDict, JSONList)