# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2014, FBReader.ORG Limited <support@fbreader.org>'

from PyQt5.Qt import *

class StatusDialog(QDialog):

	def __init__(self, controller, paths, parent = None):
		QDialog.__init__(self, parent)
		self.uploaders = []
		self.paths = paths
		self.todo = len(paths)
		self.controller = controller
		self.controller.updated.connect(self.onUpdated)
		self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "fbreader", "gui")
		geom = self.settings.value("StatusDialogGeometry")
		if geom:
			self.restoreGeometry(geom)
		else:
			self.resize(800, 600)


		self.setWindowTitle("Uploading status")
		layout = QVBoxLayout()
		self.tableWidget = QTableWidget(len(paths), 4, self)
		self.tableWidget.setHorizontalHeaderLabels(("Upload?","Book", "Format", "Status"))
		self.rows = []
		for j in xrange(len(self.paths)):
			cb = QCheckBox()
			cb.setStyleSheet("margin-left:25%; margin-right:25%;")
			items = []
			itemc = CBoxItem(cb)
			itemc.setFlags(Qt.NoItemFlags)
			self.tableWidget.setItem(j, 0, itemc)
			items.append(itemc)
			self.tableWidget.setCellWidget(j, 0, cb)
			itemt = QTableWidgetItem(paths[j][1])
			itemt.setFlags(Qt.NoItemFlags)
			itemt.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 1, itemt)
			items.append(itemt)
			itemf = QTableWidgetItem(paths[j][2])
			itemf.setFlags(Qt.NoItemFlags)
			itemf.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 2, itemf)
			items.append(itemf)
			pb = QProgressBar()
			pb.setMinimum(0)
			pb.setMaximum(100)
			pb.setValue(50)
			itemp = PBarItem()
			itemp.setFlags(Qt.NoItemFlags)
			itemp.setForeground(QColor(0,0,0))
			p = pb.palette()
			p.setColor(QPalette.Highlight, StatusRow.color_darkgood)
			pb.setPalette(p)
			pb.setFormat("Unknown")
			self.tableWidget.setItem(j, 3, itemp)
			self.tableWidget.setCellWidget(j, 3, pb)
			items.append(itemp)
			row = StatusRow(items, pb, cb, paths[j][0])
			self.rows.append(row)
		self.tableWidget.verticalHeader().hide()
		self.tableWidget.resizeColumnsToContents()
		layout.addWidget(self.tableWidget)
		self.tableWidget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
		self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
		self.tableWidget.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
		self.tableWidget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)

		self.tableWidget.setSortingEnabled(True)

		buttons = QHBoxLayout()
		self.bstart = QPushButton("Start!")
		self.bclose = QPushButton("Close")
		self.bstart.clicked.connect(self.start)
		self.bclose.clicked.connect(self.close)
		buttons.addWidget(self.bstart)
		buttons.addWidget(self.bclose)
		layout.addLayout(buttons)
		self.setLayout(layout)
		for p in self.paths:
			self.controller.forcecheck(p[0])
		self.update()

	def closeEvent(self, event):
		self.settings.setValue("StatusDialogGeometry", self.saveGeometry())

	def start(self):
		for r in self.rows:
			if r.cbox.isChecked():
				r.cbox.setChecked(False)
				self.controller.upload(r.path)

	def update(self):
		for r in self.rows:
			r.update(self.controller.uploaders)

	def onUpdated(self):
		self.update()
		self.repaint()

class StatusRow():

	color_lightgood = QColor(192, 255, 192)
	color_darkgood = QColor(0, 80, 0)

	color_lightbad = QColor(255, 192, 192)
	color_darkbad = QColor(80, 0, 0)


	def __init__(self, items, pb, cb, p):
		self.items = items
		self.pbar = pb
		self.cbox = cb
		self.path = p

	def update(self, uploaders):
		text = ''
		lightcolor = Qt.white
		darkcolor = self.color_darkgood
		progress = 0
		tooltip = ''
		if self.path in uploaders.keys():
			uploader = uploaders[self.path]
			with uploader.lock:
				if uploader.status.error:
					darkcolor = self.color_darkbad
					lightcolor = self.color_lightbad
					text = "Error"
					progress = 100
					tooltip = uploader.status.error_message
				elif uploader.status.inprocess:
					inprogress = True
					self.cbox.setEnabled(False)
					self.cbox.setChecked(False)
					if not uploader.status.exists.known():
						text = "Checking"
					else:
						text = "Uploading"
						progress = uploader.progress
				else:
					self.cbox.setEnabled(True)
					if uploader.status.uploaded.known():
						if uploader.status.uploaded.value():
							self.cbox.setEnabled(False)
							self.cbox.setChecked(False)
							lightcolor = self.color_lightgood
							text = "Uploaded"
							progress = 100
						else:
							darkcolor = self.color_darkbad
							lightcolor = self.color_lightbad
							text = "Error"
					elif uploader.status.exists.known():
						if uploader.status.exists.value():
							self.cbox.setEnabled(False)
							self.cbox.setChecked(False)
							lightcolor = self.color_lightgood
							text = "Already Exists"
							progress = 100
						else:
							self.cbox.setEnabled(True)
							self.cbox.setChecked(True)
							text = "Ready"
					else:
						text = "Unknown"
		else:
			self.cbox.setEnabled(True)
			text = "Unknown"
		p = self.pbar.palette()
		p.setColor(QPalette.Highlight, darkcolor)
		self.pbar.setPalette(p)
		self.pbar.setFormat(text)
		self.pbar.setValue(progress)
		self.pbar.setToolTip(tooltip)
		self.items[0].setBackground(lightcolor)
		self.items[1].setBackground(lightcolor)
		self.items[2].setBackground(lightcolor)
		self.items[3].compvalue = uploader.status.compare_value()

class CBoxItem(QTableWidgetItem):
	def __init__(self, cb):
		QTableWidgetItem.__init__(self)
		self.cbox = cb

	def __lt__(self, other):
		return other.cbox.isChecked() and not self.cbox.isChecked()


class PBarItem(QTableWidgetItem):
	def __init__(self):
		QTableWidgetItem.__init__(self)
		self.compvalue = 0

	def __lt__(self, other):
		return self.compvalue < other.compvalue

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
		self.error_message = ''

	def compare_value(self):
		res = 0
		if self.error:
			res += 1000
		res += self.uploaded._value_ * 100
		if self.inprocess:
			res += 10
		res += self.exists._value_ * 1
		return res

	def __lt__(self, other):
		return self.compare_value() > other.compare_value()

