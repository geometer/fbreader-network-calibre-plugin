# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

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

BLOCKSIZE = 65536
DOMAIN = "books.fbreader.org"
BASE_URL = "https://books.fbreader.org/"

class FBReaderUploadAction(InterfaceAction):

	name = 'Upload to FBReader'
	action_spec = ('Upload to FBReader', None, None, None)
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
		if not rows or len(rows) == 0:
			return error_dialog(self.gui, 'No books selected',
								'You must select one or more books to perform this action.', show=True)
		login = self.check_login()
		if login == 1:#not authorized
			msgBox = QMessageBox()
			msgBox.setWindowTitle("Not authorized")
			msgBox.setText("Would you kindly login into books.fbreader.org?")
			msgBox.exec_()
			self.open()
			if self.check_login() != 0:
				return error_dialog(self.gui, 'You still not authorized!',
									'Shame on you!', show=True)
		elif login != 0:
			return error_dialog(self.gui, 'Error',
									'Something awful happened!', show=True)
		book_ids = self.gui.library_view.get_selected_ids()
		db = self.gui.library_view.model().db

		paths = []

		for book_id in book_ids:
			mi = db.get_metadata(book_id, index_is_id=True, get_user_categories=False)
			title, formats = mi.title, mi.formats
			for f in formats:
				path = db.format_abspath(book_id, f, index_is_id=True)
				paths.append(path)
		StatusDialog(self.controller, paths, self.gui).exec_()

	def open(self):
		from calibre.gui2.store.web_store_dialog import WebStoreDialog
		d = WebStoreDialog(self.gui, "https://books.fbreader.org/catalog", None, None, create_browser=self.create_browser)
		d.setWindowTitle("FBReader® Book Network")
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


class StatusDialog(QDialog):

	def __init__(self, controller, paths, parent = None):
		QDialog.__init__(self, parent)
		self.uploaders = []
		self.paths = paths
		self.todo = len(paths)
		self.controller = controller
		self.controller.updated.connect(self.onUpdated)


		self.setWindowTitle("Uploading status")
		layout = QVBoxLayout()
		self.tableWidget = QTableWidget(len(paths), 3, self)
		self.tableWidget.setHorizontalHeaderLabels(("Upload?","file", "status"))
		for j in xrange(len(self.paths)):
			path = paths[j]
			cb = QCheckBox()
			cb.setChecked(True)
			cb.setStyleSheet("margin-left:25%; margin-right:25%;")
			item = QTableWidgetItem()
			item.setFlags(Qt.NoItemFlags)
			self.tableWidget.setItem(j, 0, item)
			self.tableWidget.setCellWidget(j, 0, cb)
			item = QTableWidgetItem(os.path.basename(path))
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 1, item)
			item = QTableWidgetItem("Unknown")
			item.setFlags(Qt.NoItemFlags)
			item.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 2, item)
		self.tableWidget.verticalHeader().hide()
		self.tableWidget.resizeColumnsToContents()
		layout.addWidget(self.tableWidget)
		self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.tableWidget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

		box = QDialogButtonBox(QDialogButtonBox.Ok, Qt.Horizontal)
		layout.addWidget(box)
		self.setLayout(layout)

		self.ok = box.button(QDialogButtonBox.Ok)
		self.ok.setEnabled(False)
		self.ok.clicked.connect(self.close)
		for p in self.paths:
			self.controller.check(p)
		self.update()

	def update(self):
		for i in xrange(len(self.paths)):
			p = self.paths[i]
			text = self.tableWidget.item(i, 2).text()
			color = self.tableWidget.item(i, 2).background().color()
			if p in self.controller.uploaders.keys():
				uploader = self.controller.uploaders[p]
				with uploader.lock:
					if uploader.status.error:
						color = QColor(255, 127, 127)
						text = "Error"
					elif uploader.status.inprocess:
						if not uploader.status.exists.known():
							color = QColor(255, 255, 255)
							text = "Checking"
						else:
							color = QColor(255, 255, 255)
							text = "Uploading"
					else:
						if uploader.status.uploaded.known():
							if uploader.status.uploaded.value():
								color = QColor(127, 255, 127)
								text = "Uploaded"
							else:
								color = QColor(255, 127, 127)
								text = "Error"
						elif uploader.status.exists.known():
							if uploader.status.exists.value():
								color = QColor(127, 255, 127)
								text = "Already Exists"
							else:
								color = QColor(255, 255, 255)
								text = "Ready"
						else:
							color = QColor(255, 255, 255)
							text = "Unknown"
			else:
				color = QColor(255, 255, 255)
				text = "Unknown"
			self.tableWidget.item(i, 2).setText(text)
			self.tableWidget.item(i, 2).setBackground(color)

	def onUpdated(self):
		self.update()
		self.repaint()

class UploadController(QObject):

	updated = pyqtSignal()

	def __init__(self, parent=None):
		QObject.__init__(self, parent)
		self.uploaders = {}

	def __create_uploader__(self, p):
		if p not in self.uploaders.keys():
				upl = Uploader(p, self)
				upl.updated.connect(self.onUpdated)
				self.uploaders[p] = upl

	def check(self, path):
		self.__create_uploader__(path)
		self.uploaders[path].check()

	def upload(self, path):
		self.__create_uploader__(path)
		self.uploaders[path].upload()

	def onUpdated(self):
		self.updated.emit()



class b3:
	value_flag = 1
	known_flag = 2

	def __init__(self):
		self._value_ = 0

	def set_value(self, value):
		if value:
			self._value_ = 3
		else:
			self._value_ = 2

	def known(self):
		return self._value_ & self.known_flag

	def value(self):
		return self._value_ & self.value_flag

class Status:
	def __init__(self):
		self.exists = b3()
		self.uploaded = b3()
		self.inprocess = False
		self.error = False



class Uploader(QObject):

	updated = pyqtSignal()

	def __init__(self, path, parent=None):
		QObject.__init__(self, parent)
		self.url = BASE_URL + "app/book.upload"
		self.path = path
		self.manager = QNetworkAccessManager(self)
		self.manager.setCookieJar(MyNetworkCookieJar(False, self))
		self.status = Status()
		self.progress = 0
		self.lock = threading.RLock() #FIXME I hope it works with qt threads
		self.need_upload = False

	def check(self):
		with self.lock:
			if self.status.inprocess:
				return
			if self.status.exists.known():
				return
			self.status.inprocess = True
			self.reply = self.__check__()
			self.reply.finished.connect(self.onCheck)

	def upload(self):
		with self.lock:
			if self.status.inprocess:
				self.need_upload = True
				return
			if not self.status.exists.known():
				self.status.inprocess = True
				self.reply = self.__check__()
				self.reply.finished.connect(self.onCheckAndUpload)
			elif not self.status.exists.value():
				self.status.inprocess = True
				self.__upload__()

	def onCheck(self):
		self.onCheckAndMaybeUpload(self.need_upload, self.sender())

	def onCheckAndUpload(self):
		self.onCheckAndMaybeUpload(True, self.sender())

	def onCheckAndMaybeUpload(self, upload, sender):
		with self.lock:
			self.__onCheck__(sender)
			if upload and (not self.status.error) and (not self.status.exists.value):
				self.status.inprocess = True
				self.__upload__()
			else:
				self.status.inprocess = False
			self.updated.emit()

	def onUpload(self):
		with self.lock:
			self.need_upload = False
			if self.sender().error() != 0:
				self.status.error = True
				self.updated.emit()
				return
			self.status.uploaded.set_value(True)
			self.status.exists.set_value(True)
			self.updated.emit()

	def __check__(self):
		hasher = hashlib.sha1()
		with open(self.path, 'rb') as afile:
			buf = afile.read(BLOCKSIZE)
			while len(buf) > 0:
				hasher.update(buf)
				buf = afile.read(BLOCKSIZE)
		h = hasher.hexdigest()
		self.referer = BASE_URL + "app/book.status.by.hash?sha1=" + h
		self.request = QNetworkRequest(QUrl(self.referer))
		return self.manager.get(self.request)

	def __onCheck__(self, sender):
		if sender.error() != 0:
			self.status.error = True
			return
		try:
			res = json.loads(str(sender.readAll()))
			if res["status"] == "found":
				self.status.exists.set_value(True)
				return
		except Exception as e:
			self.status.error = True
			return
		self.csrftoken = None
		for c in self.manager.cookieJar().allCookies():
			if str(c.domain()) == DOMAIN and str(c.name()) == "csrftoken":
				self.csrftoken = str(c.value())
		if not self.csrftoken:
			self.status.error = True
			return
		self.status.exists.set_value(False)

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
		self.request.setRawHeader("Referer", self.referer)
		self.reply = self.manager.post(self.request, self.multiPart)
		self.reply.finished.connect(self.onUpload)


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





