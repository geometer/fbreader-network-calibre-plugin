# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2015, FBReader.ORG Limited <support@fbreader.org>'

import platform

from contextlib import closing


from calibre.gui2 import error_dialog, Dispatcher
from calibre.gui2.actions import InterfaceAction

from PyQt5.Qt import *
from cookielib import CookieJar, Cookie

import hashlib
import json
import urllib2
import os
import threading
from threading import Thread
from datetime import datetime
from time import sleep

from .status_dialog import StatusDialog, Status

BLOCKSIZE = 65536
DOMAIN = "books.fbreader.org"
BASE_URL = "https://books.fbreader.org/"

class FBReaderSyncAction(InterfaceAction):

	name = 'FBReader Sync'
	action_spec = (name, None, None, None)
	action_type = 'current'

	def genesis(self):
		pixmap = QPixmap()
		pixmap.loadFromData(self.load_resources(['fbreader.png']).itervalues().next())
		icon = QIcon(pixmap)
		self.qaction.setIcon(icon)
		self.qaction.triggered.connect(self.upload)
		self.controller = UploadController(self.gui)

	def upload(self):
		rows = self.gui.library_view.selectionModel().selectedRows()
#		if not rows or len(rows) == 0:
#			return error_dialog(self.gui, 'No books selected',
#								'Please select one or more books to perform this action.', show=True)
		login = self.check_login()
		if login == 1:#not authorized
			msgBox = QMessageBox()
			msgBox.setWindowTitle('Not authorized')
			msgBox.setText('Would you like to sign in to FBReader Book Network?')
			msgBox.exec_()
			self.open()
			if self.check_login() != 0:
				return error_dialog(self.gui, 'Error', 'You are not authorised', show=True)
		elif login != 0:
			return error_dialog(self.gui, 'Error', 'Something went wrong', show=True)
		book_ids = self.gui.library_view.get_selected_ids()
		db = self.gui.library_view.model().db
		model = self.gui.library_view.model()
		all_ids = []
		
		for i in range(model.rowCount(None)):
			all_ids.append(model.id(i))

		paths = []
		allpaths = []

		for book_id in all_ids:
			mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
			title, formats = mi.title, mi.formats
			for f in formats:
				path = db.format_abspath(book_id, f, index_is_id=True)
				name = title
				allpaths.append((path, name, f))
				if book_id in book_ids:
					paths.append(path)
		StatusDialog(self.controller, allpaths, paths, self.gui).exec_()

	def open(self):
		from calibre.gui2.store.web_store_dialog import WebStoreDialog
		d = WebStoreDialog(self.gui, "https://books.fbreader.org/catalog", None, None, create_browser=self.create_browser)
		d.setWindowTitle("FBReader Book Network")
		d.view.cookie_jar = MyNetworkCookieJar(True)
		d.view.page().networkAccessManager().setCookieJar(d.view.cookie_jar)
		d.exec_()


	def create_browser(self):
		from calibre import browser
		br = browser()
		for cookie in MyNetworkCookieJar().py_cookies:
			br.cookiejar.set_cookie(cookie)
		return br
				
	def check_login(self):
		req = urllib2.Request("https://books.fbreader.org/opds")
		qjar = MyNetworkCookieJar(False)
		jar = CookieJar()
		for cookie in qjar.py_cookies:
			jar.set_cookie(cookie)
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))
		req.add_header('X-Accept-Auto-Login', "True")
		try:
			response = opener.open(req)
			return 0
		except urllib2.HTTPError as e:
			if e.code == 401:
				return 1
		except:
			return 2
		return 2  # What can we do here???


class UploadController(QObject):


	hashed = pyqtSignal(object)
	hashed1 = pyqtSignal(object)

	CHECK_NUM = 90

	def __init__(self, parent=None):
		QObject.__init__(self, parent)
		self.uploaders = {}
		self.manager = QNetworkAccessManager(self)
		self.manager.setCookieJar(MyNetworkCookieJar(False, self))
		self.replies = set()
		self.hashed.connect(self.onHashInternal)

	def get_uploader(self, p):
		if p not in self.uploaders.keys():
				upl = Uploader(p, self)
				self.uploaders[p] = upl
		return self.uploaders[p]

	def hash_all(self, paths):
		print('hash start' + str(datetime.now()))
		hashes = {}
		hasheslist = []
		for p in paths:
			u = self.get_uploader(p[0])
			with u.lock:
				if not u.status.inprocess:
					u.status = Status()
					u.status.inprocess = True
	#				u.updated.emit()
					if not u.hash:
						u.prepare_hash()
	#				else:
	#					sleep(0.01)
					hashes[u.hash] = u
					if len(hashes.keys()) >= self.CHECK_NUM:
						self.hashed.emit(hashes)
						hasheslist.append(hashes)
						hashes = {}
				else:
					u.updated.emit()
		self.hashed.emit(hashes)
		hasheslist.append(hashes)
#		self.hashed.emit(hasheslist)
#		self.hashed1.emit()
		print('hashed' + str(datetime.now()))
		

	def check_all(self, paths):
		thread = Thread(target = lambda: self.hash_all(paths))
		thread.start()


	def onHash(self, hasheslist): #TODO: some synchronization?
		for hashes in hasheslist:
			self.onHashInternal(hashes)

	def onHashInternal(self, hashes):
		print('some hashed...' + str(datetime.now()))
		url = BASE_URL + "app/books.by.hashes?hashes=" #FIXME: better post parameters processing
		for h in hashes.keys():
			url += (h + ',')
		url = url[:-1]
		request = QNetworkRequest(QUrl(url))
		reply = self.manager.get(request)
		reply.finished.connect(lambda: self.onCheck(hashes))
		self.replies.add(reply)
		print('some checking...' + str(datetime.now()))

	def onCheck(self, hashes):
		print('some checked...' + str(len(hashes.keys())) + str(datetime.now()))
		r = self.sender()
		if r.error() != 0:
			print(r.error())
			return
		try:
			res = json.loads(str(r.readAll()))
			self.replies.remove(r)
			r.deleteLater()
			csrftoken = ''
			for c in self.manager.cookieJar().allCookies():
				if str(c.domain()) == DOMAIN and str(c.name()) == "csrftoken":
					csrftoken = str(c.value())
			for b in res:
				for h in b['hashes']:
					if h in hashes.keys():
						u = hashes[h]
						with u.lock:
							u.status.exists.set_value(True)
							u.status.inprocess = False
							u.updated.emit()
			for u in hashes.values():
				u.csrftoken = csrftoken
				with u.lock:
					if not u.status.exists.known():
						u.status.exists.set_value(False)
						u.status.inprocess = False
						u.updated.emit()
			return
		except Exception as e:
			print(e)
			return
			
	def upload(self, path):
		self.get_uploader(path).upload()



import resource
import fcntl
import os

def get_open_fds():
    fds = []
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    for fd in range(0, soft):
        try:
            flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        except IOError:
            continue
        fds.append(fd)
    return fds

class My_Runnable(QRunnable):
	def __init__(self, func):
		QRunnable.__init__(self)
		self.func = func

	def run(self):
		apply(self.func)


class Uploader(QObject):

	updated = pyqtSignal()
	hashed = pyqtSignal()

	def __init__(self, path, parent=None):
		QObject.__init__(self, parent)
		self.url = BASE_URL + "app/book.upload"
		self.path = path
		self.status = Status()
		self.progress = 0
		self.lock = threading.RLock()
		self.hash = None


	def upload(self):
		with self.lock:
			if self.status.inprocess:
				return
			if not self.status.exists.known():
				return
			elif not self.status.exists.value():
				self.status.inprocess = True
				self.__upload__()
			self.updated.emit()

	def onUpload(self):
		with self.lock:
			self.need_upload = False
			self.status.inprocess = False
			self.__onUpload__(self.sender())
			self.reply.deleteLater()
			self.reply = None
			self.updated.emit()

	def __onUpload__(self, sender):
		if sender.error() != 0:
			self.status.error = True
			return
		try:
			data = self.sender().readAll()
			res = json.loads(str(data))
			if 'error' in res[0]['result'].keys():
				self.status.error = True
				self.status.error_message = res[0]['result']['error']
				return
			self.status.uploaded.set_value(True)
			self.status.exists.set_value(True)
		except Exception as e:
			self.status.error = True
			return

	def prepare_hash(self):
		if not self.hash:
			hasher = hashlib.sha1()
			with open(self.path, 'rb') as afile:
				buf = afile.read(BLOCKSIZE)
				while len(buf) > 0:
					hasher.update(buf)
					buf = afile.read(BLOCKSIZE)
			self.hash = hasher.hexdigest()

	def __upload__(self):
		self.multiPart = QHttpMultiPart(QHttpMultiPart.FormDataType, self)
		self.filePart = QHttpPart()
		self.filePart.setHeader(QNetworkRequest.ContentDispositionHeader, QVariant("form-data; name=\"file\"; filename=\"" + os.path.basename(self.path) + "\""));
		self.qfile = QFile(self.path, self)
		self.qfile.open(QIODevice.ReadOnly)
		self.filePart.setBodyDevice(self.qfile)
		self.multiPart.append(self.filePart)
		self.request = QNetworkRequest(QUrl(self.url))
		self.request.setRawHeader("X-CSRFToken", self.csrftoken)
		self.request.setRawHeader("Referer", BASE_URL + "app/books.by.hashes")
		self.reply = self.parent().manager.post(self.request, self.multiPart)
		self.reply.finished.connect(self.onUpload)
		self.reply.uploadProgress.connect(self.onProgress)

	def onProgress(self, s, t):
		if (t != 0):
			self.progress = int(100. * s / t)
			self.updated.emit()


#================= from another plugin

class MyNetworkCookieJar(QNetworkCookieJar):
	def __init__(self, writable, parent=None):
		QNetworkCookieJar.__init__(self, parent)
		self.readonly = not writable
		self.storage = QSettings(QSettings.IniFormat, QSettings.UserScope, "fbreader", "plugin")
		self.loadCookies()

	def setCookiesFromUrl(self, cookieList, url):
		res = QNetworkCookieJar.setCookiesFromUrl(self, cookieList, url)
		self.saveCookies()
		return res

	def saveCookies(self):
		if self.readonly:
			return
		cookies = QByteArray()
		for cookie in self.allCookies():
			if not cookie.isSessionCookie():
				cookies.append(cookie.toRawForm())
				cookies.append("\n")
		self.storage.setValue("cookies", cookies)

	def loadCookies(self):
		tmp = self.storage.value("cookies")
		if not tmp:
			return
		cookieList = QNetworkCookie.parseCookies(tmp)
		self.setAllCookies(cookieList)

	def py_cookies_internal(self):
		for c in self.allCookies():
			name, value = map(bytes, (c.name(), c.value()))
			domain = bytes(c.domain())
			initial_dot = domain_specified = domain.startswith(b'.')
			secure = bool(c.isSecure())
			path = unicode(c.path()).strip().encode('utf-8')
			expires = c.expirationDate()
			is_session_cookie = False
			if expires.isValid():
				expires = expires.toTime_t()
			else:
				expires = None
				is_session_cookie = True
			path_specified = True
			if not path:
				path = b'/'
				path_specified = False
			c = Cookie(0,  # version
					name, value,
					None,  # port
					False,  # port specified
					domain, domain_specified, initial_dot, path,
					path_specified,
					secure, expires, is_session_cookie,
					None,  # Comment
					None,  # Comment URL
					{}  # rest
			)
			yield c
	@property
	def py_cookies(self):
		'''
		Return all the cookies set currently as :class:`Cookie` objects.
		Returns expired cookies as well.
		'''
		return list(self.py_cookies_internal())





