# Copyright 2012 Google Inc. All Rights Reserved.

"""Tests for cloudstorage_api.py."""



import hashlib
import math
import os
import time
import unittest

from  import 
from google.appengine.ext import testbed
from . import cloudstorage_api
from . import errors
from . import stub_dispatcher


BUCKET = '/bucket'
TESTFILE = BUCKET + '/testfile'
DEFAULT_CONTENT = ['a'*1024*257,
                   'b'*1024*257,
                   'c'*1024*257]


class CloudStorageTest(unittest.TestCase):
  """Test for cloudstorage."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_app_identity_stub()
    self.testbed.init_blobstore_stub()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_urlfetch_stub()
    self._old_max_keys = stub_dispatcher._MAX_GET_BUCKET_RESULT
    stub_dispatcher._MAX_GET_BUCKET_RESULT = 2
    self.start_time = time.time()

  def tearDown(self):
    stub_dispatcher._MAX_GET_BUCKET_RESULT = self._old_max_keys
    self.testbed.deactivate()

  def CreateFile(self, filename):
    f = cloudstorage.open(filename,
                          'w',
                          'text/plain',
                          {'x-goog-meta-foo': 'foo',
                           'x-goog-meta-bar': 'bar'})
    for content in DEFAULT_CONTENT:
      f.write(content)
    f.close()

  def testDelete(self):
    self.assertRaises(errors.NotFoundError, cloudstorage.delete, TESTFILE)
    self.CreateFile(TESTFILE)
    cloudstorage.delete(TESTFILE)
    self.assertRaises(errors.NotFoundError, cloudstorage.delete, TESTFILE)
    self.assertRaises(errors.NotFoundError, cloudstorage.stat, TESTFILE)

  def testReadEntireFile(self):
    f = cloudstorage.open(TESTFILE, 'w')
    f.write('abcde')
    f.close()

    f = cloudstorage.open(TESTFILE, read_buffer_size=1)
    self.assertEqual('abcde', f.read())
    f.close()

    f = cloudstorage.open(TESTFILE)
    self.assertEqual('abcde', f.read(8))
    f.close()

  def testReadSmall(self):
    f = cloudstorage.open(TESTFILE, 'w')
    f.write('abcdefghij')
    f.close()

    f = cloudstorage.open(TESTFILE, read_buffer_size=3)
    self.assertEqual('ab', f.read(2))
    self.assertEqual('c', f.read(1))
    self.assertEqual('de', f.read(2))
    self.assertEqual('fghij', f.read())
    f.close()

  def testWriteRead(self):
    f = cloudstorage.open(TESTFILE, 'w')
    f.write('a')
    f.write('b'*1024)
    f.write('c'*1024 + '\n')
    f.write('d'*1024*1024)
    f.write('e'*1024*1024*10)
    self.assertRaises(errors.NotFoundError, cloudstorage.stat, TESTFILE)
    f.close()

    f = cloudstorage.open(TESTFILE)
    self.assertEqual('a' + 'b'*1024, f.read(1025))
    self.assertEqual('c'*1024 + '\n', f.readline())
    self.assertEqual('d'*1024*1024, f.read(1024*1024))
    self.assertEqual('e'*1024*1024*10, f.read())
    self.assertEqual('', f.read())
    self.assertEqual('', f.readline())

  def testSeekAndTell(self):
    f = cloudstorage.open(TESTFILE, 'w')
    f.write('abcdefghij')
    f.close()

    f = cloudstorage.open(TESTFILE)
    f.seek(5)
    self.assertEqual(5, f.tell())
    self.assertEqual('f', f.read(1))
    self.assertEqual(6, f.tell())
    f.seek(-1, os.SEEK_CUR)
    self.assertEqual('f', f.read(1))
    f.seek(-1, os.SEEK_END)
    self.assertEqual('j', f.read(1))

  def testStat(self):
    self.CreateFile(TESTFILE)
    filestat = cloudstorage.stat(TESTFILE)
    content = ''.join(DEFAULT_CONTENT)
    self.assertEqual(len(content), filestat.st_size)
    self.assertEqual('text/plain', filestat.content_type)
    self.assertEqual('foo', filestat.metadata['x-goog-meta-foo'])
    self.assertEqual('bar', filestat.metadata['x-goog-meta-bar'])
    self.assertEqual(TESTFILE, filestat.filename)
    self.assertEqual(hashlib.md5(content).hexdigest(), filestat.etag)
    self.assertTrue(math.floor(self.start_time) <= filestat.st_ctime)
    self.assertTrue(filestat.st_ctime <= time.time())

  def testListBucket(self):
    bars = [BUCKET + '/test/bar' + str(i) for i in range(3)]
    foos = [BUCKET + '/test/foo' + str(i) for i in range(3)]
    filenames = bars + foos
    for filename in filenames:
      self.CreateFile(filename)

    bucket = cloudstorage.listbucket(BUCKET, prefix='test/')
    self.assertEqual(filenames, [stat.filename for stat in bucket])

    bucket = cloudstorage.listbucket(BUCKET, prefix='test/', max_keys=1)
    stats = list(bucket)
    self.assertEqual(1, len(stats))
    stat = stats[0]
    content = ''.join(DEFAULT_CONTENT)
    self.assertEqual(filenames[0], stat.filename)
    self.assertEqual(len(content), stat.st_size)
    self.assertEqual(hashlib.md5(content).hexdigest(), stat.etag)

    bucket = cloudstorage.listbucket(BUCKET,
                                     prefix='test/',
                                     marker='test/foo0',
                                     max_keys=1)
    stats = [stat for stat in bucket]
    self.assertEqual(1, len(stats))
    stat = stats[0]
    self.assertEqual(foos[1], stat.filename)


if __name__ == '__main__':
  unittest.main()
