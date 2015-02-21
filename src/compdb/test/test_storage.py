import unittest
from contextlib import contextmanager

from compdb.core.storage import ReadOnlyStorage, Storage

import os
CWD = os.getcwd()

def make_test_data():
    import uuid
    return str(uuid.uuid4())

def make_test_fn():
    import uuid
    return format('_file_{}'.format(uuid.uuid4()))

def get_test_file():
    return make_test_fn(), make_test_data()

@contextmanager
def get_storage(name = None):
    from compdb.core.config import read_config
    config = read_config()
    import os, shutil
    if name is None:
        import uuid
        name = str(uuid.uuid4())
    fs_path = os.path.realpath(os.path.join(CWD, config['filestorage_dir'], name))
    fs_path = os.path.realpath(os.path.join(CWD, config['filestorage_dir'], name))
    wd_path = os.path.realpath(os.path.join(CWD, config['working_dir']))
    if not os.path.isdir(fs_path):
        os.mkdir(fs_path)
    cwd = os.getcwd()
    os.chdir(wd_path)
    storage = Storage(fs_path = fs_path, wd_path = wd_path)
    error = None
    try:
        yield storage
    except Exception as error:
        raise
    finally:
        storage.remove()
        os.chdir(cwd)

@contextmanager
def get_readonly_storage(name = None):
    from compdb.core.config import read_config
    config = read_config()
    import os,shutil
    if name is None:
        import uuid
        name = str(uuid.uuid4())
    fs_path = os.path.realpath(os.path.join(CWD, config['filestorage_dir'], name))
    wd_path = os.path.realpath(os.path.join(CWD, config['working_dir']))
    cwd = os.getcwd()
    os.chdir(wd_path)
    storage = ReadOnlyStorage(fs_path = fs_path, wd_path = wd_path)
    error = None
    try:
        yield storage
    except Exception as error:
        raise
    finally:
        os.chdir(cwd)

@contextmanager 
def test_file(fn = None):
    import uuid, os
    if fn is None:
        fn = make_test_fn()
    data = make_test_data().encode()
    with open(fn, 'wb') as file:
        file.write(data)
    try:
        yield fn, data
    except Exception:
        raise
    finally:
        try:
            os.remove(fn)
        except Exception:
            pass

class TestReadOnlyStorage(unittest.TestCase):

    def test_construction(self):
        name = 'test_readonly_construction'
        with get_storage(name) as storage:
            get_readonly_storage(name)

    def test_download_file(self):
        import os
        from os.path import isfile
        name = 'test_download_file'
        with get_storage(name) as storage:
            with get_readonly_storage(name) as rostorage:
                with test_file() as (fn, data):
                    self.assertTrue(isfile(fn))
                    storage.store_file(fn)
                    self.assertFalse(isfile(fn))
                    rostorage.download_file(fn)
                    self.assertTrue(isfile(fn))
                    os.remove(fn)

class TestStorage(unittest.TestCase):

    def test_construction(self):
        get_storage()

    def test_file_store_and_restore(self):
        from os.path import isfile
        with get_storage() as storage:
            with test_file() as (fn, data):
                self.assertTrue(isfile(fn))
                storage.store_file(fn)
                self.assertFalse(isfile(fn))
                storage.restore_file(fn)
                self.assertTrue(isfile(fn))
                with open(fn, 'rb') as file:
                    read_back = file.read()
            self.assertEqual(read_back, data)

    def test_open_new_file(self):
        from os.path import isfile
        fn, data = get_test_file()
        with get_storage() as storage:
            with storage.open_file(fn, 'wb') as file:
                file.write(data.encode())
            self.assertFalse(isfile(fn))
            storage.restore_file(fn)
            with open(fn, 'rb') as file:
                self.assertEqual(file.read().decode(), data)
            storage.store_file(fn)

    def test_reopen_file(self):
        from os.path import isfile
        fn, data = get_test_file()
        with get_storage() as storage:
            with storage.open_file(fn, 'wb') as file:
                file.write(data.encode())
            with storage.open_file(fn, 'rb') as file:
                self.assertEqual(file.read().decode(), data)

    def test_remove_file(self):
        from os.path import isfile
        fn, data = get_test_file()
        with get_storage() as storage:
            with storage.open_file(fn, 'wb') as file:
                file.write(data.encode())
            storage.remove_file(fn)
            with self.assertRaises(FileNotFoundError):
                storage.restore_file(fn)

    def test_list_files(self):
        from os.path import isfile
        num_files = 20
        files = [get_test_file() for i in range(num_files)]
        with get_storage() as storage:
            for fn, data in files:
                with storage.open_file(fn, 'wb') as file:
                    file.write(data.encode())

            fn_i = [e[0] for e in files]
            fn_s = storage.list_files()
            self.assertEqual(set(fn_i), set(fn_i))

    def test_store_files(self):
        import os
        from os.path import isfile
        num_files = 20
        files = [get_test_file() for i in range(num_files)]
        with get_storage() as storage:
            for fn, data in files:
                with open(fn, 'wb') as file:
                    file.write(data.encode())
            fn_i = [e[0] for e in files]
            [self.assertTrue(isfile(fn)) for fn in fn_i]
            storage.store_files()
            fn_s = storage.list_files()
            self.assertEqual(set(fn_i), set(fn_i))

    def test_store_and_restore_files(self):
        import os
        from os.path import isfile
        num_files = 20
        files = [get_test_file() for i in range(num_files)]
        with get_storage() as storage:
            for fn, data in files:
                with open(fn, 'wb') as file:
                    file.write(data.encode())
            fn_i = [e[0] for e in files]
            [self.assertTrue(isfile(fn)) for fn in fn_i]
            storage.store_files()
            fn_s = storage.list_files()
            self.assertEqual(set(fn_i), set(fn_i))
            storage.restore_files()
            [self.assertTrue(isfile(fn)) for fn in fn_i]
            storage.store_files() # for automatic deletion

class TestNestedStorage(unittest.TestCase):

    def test_nested_storage(self):
        from os.path import isfile
        with get_storage() as storage:
            with get_storage() as storage2:
                with test_file() as (fn, data):
                    self.assertTrue(isfile(fn))
                    storage2.store_file(fn)
                    self.assertFalse(isfile(fn))
                    storage2.restore_file(fn)
                    self.assertTrue(isfile(fn))
            with test_file() as (fn, data):
                self.assertTrue(isfile(fn))
                storage.store_file(fn)
                self.assertFalse(isfile(fn))
                storage.restore_file(fn)
                self.assertTrue(isfile(fn))

    def test_across_nested_storage(self):
        from os.path import isfile
        with get_storage() as storage:
            with test_file() as (fn, data):
                self.assertTrue(isfile(fn))
                storage.store_file(fn)
                self.assertFalse(isfile(fn))
                with get_storage() as storage2:
                    import os
                    cwd = os.getcwd()
                    os.mkdir('tmp')
                    os.chdir('tmp')
                    storage.restore_file(fn)
                    self.assertFalse(isfile(fn))
                    storage.store_file(fn)
                    os.chdir(cwd)
                    os.rmdir('tmp')

    def test_download_file(self):
        import os
        from os.path import isfile
        with get_storage() as storage:
            with test_file() as (fn, data):
                self.assertTrue(isfile(fn))
                storage.store_file(fn)
                self.assertFalse(isfile(fn))
                with get_storage() as storage2:
                    storage.download_file(fn)
                    self.assertTrue(isfile(fn))
                    os.remove(fn)

    def test_fetch_file(self):
        import os
        from os.path import isfile
        with get_storage() as storage:
            with test_file() as (fn, data):
                self.assertTrue(isfile(fn))
                storage.store_file(fn)
                self.assertFalse(isfile(fn))
                with get_storage() as storage2:
                    storage2.fetch_file(storage, fn)
                    storage2.restore_file(fn)
                    self.assertTrue(isfile(fn))
                    storage2.store_file(fn)

if __name__ == '__main__':
    unittest.main()
