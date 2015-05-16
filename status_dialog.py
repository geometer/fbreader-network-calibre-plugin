# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'MIT'
__copyright__ = '2015, FBReader.ORG Limited <support@fbreader.org>'

from PyQt5.Qt import *
from threading import Thread
from datetime import datetime

class StatusDialog(QDialog):

	inited = pyqtSignal()

	def __init__(self, controller, allpaths, paths, parent = None):
		QDialog.__init__(self, parent)
		self.allpaths = allpaths
		self.paths = paths
#		self.todo = len(allpaths)
		self.controller = controller
		self.controller.hashed1.connect(self.update_all)
		self.settings = QSettings(QSettings.IniFormat, QSettings.UserScope, "fbreader", "gui")
		self.filter = Filter()
		formats = []
		for p in self.allpaths:
			f = p[2]
			if f not in formats:
				formats.append(f)
		formats = sorted(formats)
		geom = self.settings.value("StatusDialogGeometry")
		if geom:
			self.restoreGeometry(geom)
		else:
			self.resize(800, 600)


		self.setWindowTitle("Sync status")
		layout = QVBoxLayout()
		filter_layout = QHBoxLayout()
		lf = QLabel("Format filter: ")
		filter_layout.addWidget(lf)
		fcbox = QComboBox()
		fcbox.addItem('All')
		fcbox.addItems(formats)
		fcbox.currentIndexChanged[str].connect(self.onFormatChanged)
		filter_layout.addWidget(fcbox)

		ls = QLabel('Status filter: ')
		filter_layout.addWidget(ls)
		scbox = QComboBox()
		scbox.addItems(('All', 'Unknown', 'Checking', 'Ready', 'Synchronised', 'Uploading', 'Uploaded', 'Error'))
		scbox.currentIndexChanged[str].connect(self.onStatusChanged)
		filter_layout.addWidget(scbox)

		layout.addLayout(filter_layout)

		self.tableWidget = QTableWidget(len(allpaths), 4, self)
		self.tableWidget.setHorizontalHeaderLabels(('Select', 'Book', 'Format', 'Status'))
		self.rows = []
		for j in xrange(len(self.allpaths)):
			cb = QCheckBox()
			cb.setStyleSheet("margin-left:25%; margin-right:25%;")
			items = []
			itemc = CBoxItem(cb)
			itemc.setFlags(Qt.NoItemFlags)
			self.tableWidget.setItem(j, 0, itemc)
			items.append(itemc)
			self.tableWidget.setCellWidget(j, 0, cb)
			itemt = QTableWidgetItem(allpaths[j][1])
			itemt.setFlags(Qt.NoItemFlags)
			itemt.setForeground(QColor(0,0,0))
			self.tableWidget.setItem(j, 1, itemt)
			items.append(itemt)
			itemf = QTableWidgetItem(allpaths[j][2])
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
			pb.setFormat("Checking")
			self.tableWidget.setItem(j, 3, itemp)
			self.tableWidget.setCellWidget(j, 3, pb)
			items.append(itemp)
			row = StatusRow(self, items, pb, cb, self.controller.get_uploader(allpaths[j][0]))
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
		self.load_filter(fcbox, scbox)
		self.setLayout(layout)

	def exec_(self):
		QTimer.singleShot(10, self.checkall)
		QDialog.exec_(self)
		

	def checkall(self):
		print('checkall' + str(datetime.now()))
		self.controller.check_all(self.allpaths)
		self.update()

	def update_all(self):
		print('updateall' + str(datetime.now()))
		thread = Thread(target = lambda: self.update_all_internal())
		thread.start()

	def update_all_internal(self):
		for r in self.rows:
			r.update()

	def closeEvent(self, event):
		self.settings.setValue("StatusDialogGeometry", self.saveGeometry())
		self.save_filter()

	def start(self):
		for r in self.rows:
			if r.cbox.isChecked():
				pass
				r.cbox.setChecked(False)
				r.uploader.upload()

	def onFormatChanged(self, f):
		self.filter.format_filter = f
		self.applyfilter_global()

	def onStatusChanged(self, s):
		self.filter.status_filter = s
		self.applyfilter_global()

	def applyfilter_global(self):
		for i in xrange(self.tableWidget.rowCount()):
			self.applyfilter(i)

	def applyfilter(self, row):
		f = self.tableWidget.item(row, 2).text()
		s = self.tableWidget.cellWidget(row, 3).format()
		if (self.filter.format_filter != 'All' and self.filter.format_filter != f) or (self.filter.status_filter != 'All' and self.filter.status_filter != s):
			self.tableWidget.setRowHidden(row, True)
		else:
			self.tableWidget.setRowHidden(row, False)

	def save_filter(self):
		self.settings.setValue("FORMAT_FILTER", self.filter.format_filter)
		self.settings.setValue("STATUS_FILTER", self.filter.status_filter)

	def load_filter(self, fcbox, scbox):
		ff = self.settings.value("FORMAT_FILTER")
		sf = self.settings.value("STATUS_FILTER")
		n = fcbox.findText(ff)
		if n != -1:
			fcbox.setCurrentIndex(n)
		n = scbox.findText(ff)
		if n != -1:
			scbox.setCurrentIndex(n)
		
		
class Filter():

	def __init__(self):
		self.format_filter = 'All'
		self.status_filter = 'All'

class StatusRow():

	color_lightgood = QColor(192, 255, 192)
	color_darkgood = QColor(0, 80, 0)

	color_lightbad = QColor(255, 192, 192)
	color_darkbad = QColor(80, 0, 0)


	def __init__(self, d, items, pb, cb, up):
		self.items = items
		self.pbar = pb
		self.cbox = cb
		self.uploader = up
		self.uploader.updated.connect(self.update_async)
		self.dialog = d

	def update_async(self):
		thread = Thread(target = lambda: self.update())
		thread.start()

	def update(self):
		print('row updated1 ' + str(datetime.now()) + str(self))
		text = ''
		lightcolor = Qt.white
		darkcolor = self.color_darkgood
		progress = 0
		tooltip = ''
		with self.uploader.lock:
			if self.uploader.status.error:
				darkcolor = self.color_darkbad
				lightcolor = self.color_lightbad
				text = "Error"
				progress = 100
				tooltip = self.uploader.status.error_message
			elif self.uploader.status.inprocess:
				inprogress = True
				self.cbox.setEnabled(False)
				self.cbox.setChecked(False)
				if not self.uploader.status.exists.known():
					text = "Checking"
				else:
					text = "Uploading"
					progress = self.uploader.progress
			else:
				self.cbox.setEnabled(True)
				if self.uploader.status.uploaded.known():
					if self.uploader.status.uploaded.value():
						self.cbox.setEnabled(False)
						self.cbox.setChecked(False)
						lightcolor = self.color_lightgood
						text = "Uploaded"
						progress = 100
					else:
						darkcolor = self.color_darkbad
						lightcolor = self.color_lightbad
						text = "Error"
				elif self.uploader.status.exists.known():
					if self.uploader.status.exists.value():
						self.cbox.setEnabled(False)
						self.cbox.setChecked(False)
						lightcolor = self.color_lightgood
						text = "Synchronised"
						progress = 100
					else:
						self.cbox.setEnabled(True)
						self.cbox.setChecked(self.uploader.path in self.dialog.paths)
						text = "Ready"
				else:
					text = "Unknown"
		p = self.pbar.palette()
		print('row updated2 ' + str(datetime.now()) + str(self))
		p.setColor(QPalette.Highlight, darkcolor)
		print('row updated3 ' + str(datetime.now()) + str(self))
		self.pbar.setPalette(p)
		self.pbar.setFormat(text)
		self.pbar.setValue(progress)
		self.pbar.setToolTip(tooltip)
		print('row updated4 ' + str(datetime.now()) + str(self))
#		self.items[0].setBackground(lightcolor)
#		self.items[1].setBackground(lightcolor)
#		self.items[2].setBackground(lightcolor)
		print('row updated5 ' + str(datetime.now()) + str(self))
		self.items[3].compvalue = self.uploader.status.compare_value()
		print('row updated6 ' + str(datetime.now()) + str(self))
		self.dialog.applyfilter(self.items[0].row())
		print('row updated7 ' + str(datetime.now()) + str(self))
		self.pbar.update()
		

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


