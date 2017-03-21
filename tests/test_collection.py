import os
import io
import unittest

from signac import Collection
from signac.common import six
if six.PY2:
    from tempdir import TemporaryDirectory
else:
    from tempfile import TemporaryDirectory


class CollectionTest(unittest.TestCase):

    def setUp(self):
        self.c = Collection()

    def test_init(self):
        self.assertEqual(len(self.c), 0)

    def test_insert(self):
        doc = dict(a=0)
        self.c['0'] = doc
        self.assertEqual(len(self.c), 1)
        self.assertEqual(self.c['0'], doc)
        self.assertEqual(list(self.c.find()), [doc])
        with self.assertRaises(ValueError):
            self.c['0'] = dict(_id='1')
        with self.assertRaises(TypeError):
            self.c[0] = dict(a=0)
        with self.assertRaises(TypeError):
            self.c[1.0] = dict(a=0)

    def test_copy(self):
        docs = [dict(_id=str(i)) for i in range(10)]
        self.c.update(docs)
        c2 = Collection(self.c)
        self.assertEqual(len(self.c), len(c2))
        for doc in c2:
            self.assertEqual(len(self.c.find(doc)), 1)

    def test_insert_and_remove(self):
        doc = dict(a=0)
        self.c['0'] = doc
        self.assertEqual(len(self.c), 1)
        self.assertEqual(self.c['0'], doc)
        self.assertEqual(list(self.c.find()), [doc])
        del self.c['0']
        self.assertEqual(len(self.c), 0)
        with self.assertRaises(KeyError):
            self.assertEqual(self.c['0'], doc)

    def test_contains(self):
        self.assertFalse('0' in self.c)
        _id = self.c.insert_one(dict())
        self.assertTrue(_id in self.c)
        del self.c[_id]
        self.assertFalse(_id in self.c)
        docs = [dict(_id=str(i)) for i in range(10)]
        self.c.update(docs)
        for _id in self.c.ids:
            self.assertTrue(_id in self.c)
        for doc in docs:
            self.assertTrue(doc['_id'] in self.c)

    def test_update(self):
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c), len(docs))

    def test_index(self):
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        with self.assertRaises(KeyError):
            index = self.c.index('a')
        index = self.c.index('a', build=True)
        self.assertEqual(len(index), len(self.c))
        for value, _ids in index.items():
            for _id in _ids:
                self.assertEqual(self.c[_id]['a'], value)
        index = self.c.index('b', build=True)
        del self.c[docs[0]['_id']]
        self.assertEqual(len(self.c), len(docs)-1)
        index = self.c.index('a', build=True)
        self.assertEqual(len(index), len(self.c))
        for value, _ids in index.items():
            for _id in _ids:
                self.assertEqual(self.c[_id]['a'], value)
        self.c[docs[0]['_id']] = docs[0]
        index = self.c.index('a', build=True)
        self.assertEqual(len(index), len(self.c))
        for value, _ids in index.items():
            for _id in _ids:
                self.assertEqual(self.c[_id]['a'], value)
        self.c['0'] = dict(a=-1)
        index = self.c.index('a', build=True)
        self.assertEqual(len(index), len(self.c))
        for value, _ids in index.items():
            for _id in _ids:
                self.assertEqual(self.c[_id]['a'], value)

    def test_clear(self):
        self.assertEqual(len(self.c), 0)
        self.c['0'] = dict(a=0)
        self.assertEqual(len(self.c), 1)
        self.c.clear()
        self.assertEqual(len(self.c), 0)

    def test_iteration(self):
        self.assertEqual(len(self.c), 0)
        self.assertEqual(len(self.c.find()), 0)
        docs = self.c['0'] = dict(a=0)
        self.assertEqual(len(self.c), 1)
        self.assertEqual(len(self.c.find()), 1)
        self.c.clear()
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c), len(docs))
        self.assertEqual(len(self.c.find()), len(docs))
        self.assertEqual(
            {doc['a'] for doc in docs},
            {doc['a'] for doc in self.c.find()})

    def test_find(self):
        self.assertEqual(len(self.c.find()), 0)
        self.assertEqual(list(self.c.find()), [])
        self.assertEqual(len(self.c.find({'a': 0})), 0)
        self.assertEqual(list(self.c.find()), [])
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c.find()), len(docs))
        self.assertEqual(len(self.c.find({'a': 0})), 1)
        self.assertEqual(list(self.c.find({'a': 0}))[0], docs[0])
        self.assertEqual(len(self.c.find({'a': -1})), 0)
        self.assertEqual(len(self.c.find(limit=5)), 5)
        del self.c[docs[0]['_id']]
        self.assertEqual(len(self.c.find({'a': 0})), 0)

    def test_find_types(self):
        # Note: All of the iterables will be normalized to lists!
        t = [1, 1.0, '1', [1], tuple([1])]
        for i, t in enumerate(t):
            self.c.clear()
            doc = self.c[str(i)] = dict( a=t)
            self.assertEqual(list(self.c.find(doc)), [self.c[str(i)]])

    def test_find_one(self):
        self.assertIsNone(self.c.find_one())
        self.c.insert_one(dict())
        self.assertIsNotNone(self.c.find_one())
        self.assertEqual(len(self.c.find()), 1)

    def test_find_nested(self):
        docs = [dict(a=dict(b=i)) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c.find()), len(docs))
        self.assertEqual(len(self.c.find({'a.b': 0})), 1)
        self.assertEqual(len(self.c.find({'a': {'b': 0}})), 1)
        self.assertEqual(list(self.c.find({'a.b': 0}))[0], docs[0])
        del self.c[docs[0]['_id']]
        self.assertEqual(len(self.c.find({'a.b': 0})), 0)
        self.assertEqual(len(self.c.find({'a': {'b': 0}})), 0)

    def test_replace_one(self):
        docs = [dict(a=i) for i in range(10)]
        docs_ = [dict(a=-i) for i in range(10)]
        self.c.update(docs)
        for doc, doc_ in zip(docs, docs_):
            self.c.replace_one(doc, doc_)
        self.assertEqual(len(self.c), len(docs_))
        self.assertEqual(len(self.c.find()), len(docs_))
        self.assertEqual(
            set((doc['a'] for doc in docs_)),
            set((doc['a'] for doc in self.c.find())))

    def test_delete(self):
        self.c.delete_many({})
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c), len(docs))
        self.c.delete_many({'a': 0})
        self.assertEqual(len(self.c), len(docs)-1)
        self.c.delete_many({})
        self.assertEqual(len(self.c), 0)

    def test_delete_one(self):
        self.c.delete_one({})
        docs = [dict(a=i) for i in range(10)]
        self.c.update(docs)
        self.assertEqual(len(self.c), len(docs))
        self.c.delete_one({'a': 0})
        self.assertEqual(len(self.c), len(docs)-1)
        self.c.delete_one({})
        self.assertEqual(len(self.c), len(docs)-2)

class FileCollectionTestReadOnly(unittest.TestCase):

    def setUp(self):
        self._tmp_dir = TemporaryDirectory(prefix='signac_collection_')
        self._fn_collection = os.path.join(self._tmp_dir.name, 'test.txt')
        self.addCleanup(self._tmp_dir.cleanup)
        with Collection.open(self._fn_collection, 'w') as c:
            c.update([dict(_id=str(i)) for i in range(10)])

    def test_read(self):
        c = Collection.open(self._fn_collection, mode='r')
        self.assertEqual(len(list(c)), 10)
        self.assertEqual(len(list(c)), 10)
        self.assertEqual(len(c.find()), 10)
        c.close()

    def test_write_on_readonly(self):
        c = Collection.open(self._fn_collection, mode='r')
        self.assertEqual(len(list(c)), 10)
        c.insert_one(dict())
        self.assertEqual(len(list(c)), 11)
        with self.assertRaises(io.UnsupportedOperation):
            c.flush()
        with self.assertRaises(io.UnsupportedOperation):
            c.close()
        with self.assertRaises(RuntimeError):
            c.find()


class FileCollectionTest(CollectionTest):
    mode='w'

    def setUp(self):
        self._tmp_dir = TemporaryDirectory(prefix='signac_collection_')
        self._fn_collection = os.path.join(self._tmp_dir.name, 'test.txt')
        self.addCleanup(self._tmp_dir.cleanup)
        self.c = Collection.open(self._fn_collection, mode=self.mode)
        self.addCleanup(self.c.close)

    def test_reopen(self):
        docs = [dict(_id=str(i)) for i in range(10)]
        self.c.update(docs)
        self.c.flush()
        with Collection.open(self._fn_collection) as c:
            self.assertEqual(len(c), len(self.c))
            for doc in self.c:
                self.assertTrue(doc['_id'] in c)

class FileCollectionTestAppendPlus(FileCollectionTest):
    mode='a+'


if __name__ == '__main__':
    unittest.main()
