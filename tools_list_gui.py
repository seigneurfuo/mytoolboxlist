#!/bin/env python3

# Date de création: 2020.08.21
# Date de modification: 2021.09.23
import json
import sys
import os
import shutil
import zipfile
import platform
import subprocess
import configparser
import re

from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot, Qt, QObject, pyqtSignal, QUrl
from PyQt5.QtGui import QDesktopServices


class ApplicationArchive:
    def __init__(self, filepath):
        self.filepath = filepath
        self.foldername = Path(self.filepath).parent.name
        self.name = os.path.splitext(Path(self.filepath).name)[0]

        self.description = str()
        self.os = str()

        # self.load_metadata_from_ini()

    def __repr__(self):
        return self.filepath

    def load_metadata_from_ini(self):
        # TODO:
        if Path(metadata_filepath).exists():
            # On charge le fichier INI
            metadata = configparser.ConfigParser()
            metadata.read(metadata_filepath)

            mapper = [(self.description, 'description'),
                      (self.os, 'os')]

            for map_data in mapper:
                if map_data[1] in metadata["software"].keys():
                    map_data[0] = map_data[1]


class ExtractArchiveWorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    file_progression: int progress complete,from 0-100
    """

    current_file_progression = pyqtSignal(int, str) # pourcentage actuel


class ExtractArchiveWorker(QRunnable):
    def __init__(self, tmp_folder_path, application_archive, open_folder_after_extract):
        super(ExtractArchiveWorker, self).__init__()
        self.signals = ExtractArchiveWorkerSignals()

        self.tmp_folder_path = tmp_folder_path
        self.application_archive = application_archive
        self.open_folder_after_extract = open_folder_after_extract

    @pyqtSlot()
    def run(self):
        application_tmp_dir = Path(self.tmp_folder_path) / self.application_archive.name

        # Création du dossier de l'application
        if os.path.exists(application_tmp_dir):
            shutil.rmtree(application_tmp_dir)

        else:
            os.makedirs(application_tmp_dir)

        # Extraction du dossier (https://usefulscripting.network/python/extracting-files-with-progress/)
        try:
            with zipfile.ZipFile(self.application_archive.filepath, "r") as archive_file:
                total_elements = len(archive_file.namelist())

                for index, filename in enumerate(archive_file.namelist()):
                    percentage = int(index * (100 / total_elements))

                    # msg = "Extraction fichier {} sur {} ({}%) => {}".format(index + 1, total_elements, percentage, filename)
                    # print(msg)
                    path = os.path.join(self.application_archive.name, filename)
                    self.signals.current_file_progression.emit(percentage, path)

                    archive_file.extract(member=filename, path=application_tmp_dir)

                print("Terminé !")
                self.signals.current_file_progression.emit(0, "Terminé !")

                if self.open_folder_after_extract:
                    open_file(application_tmp_dir)

        except(IOError, zipfile.BadZipfile) as e:
            msgbox = QMessageBox()
            msgbox.setWindowTitle("Erreur problème d'extraction")
            msgbox.setText("Erreur problème d'extraction")
            msgbox.setDetailedText(str(e))
            msgbox.setIcon(QMessageBox.Critical)
            msgbox.exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        self.current_file_progression = 0

        # Config
        config_file_path = os.path.join(os.path.dirname(__file__), "config.ini")
        config = configparser.ConfigParser()
        config.read(config_file_path, encoding="utf-8")

        self.applications_path = config["config"]["root"]
        if not os.path.exists(self.applications_path):
            msg = "Le dossier <b>{}</b> n'existe pas.".format(self.applications_path)
            qmessagbox = QMessageBox(text=msg)
            qmessagbox.setWindowTitle("Erreur")
            # qmessagbox.setText("Erreur problème d'extraction")
            qmessagbox.exec()

        self.tmp_folder_path = config["config"]["tmp"]
        self.archive_extension = config["config"]["archive_extension"]
        self.metadata_file_extension = config["config"]["metadata_file_extension"]
        self.open_folder_after_extract = config["config"]["open_folder_after_extract"]

        self.thread_pool = QThreadPool()

        self.search_label = ""

        self.init_ui()
        self.init_events()

        self.applications_list = self.get_applications_list()

        self.fill_table()
        self.show()

    def init_ui(self):
        loadUi(os.path.join(os.path.dirname(__file__), "gui.ui"), self)
        # En fonction du fichier de config, on cohe cette case ou pas
        self.checkBox.setChecked(bool(int(self.open_folder_after_extract)))

    def init_events(self):
        self.pushButton.clicked.connect(self.on_launch_button_click)
        self.lineEdit.textChanged.connect(self.on_search_lineedit_content_changed)

    def get_applications_list(self):
        ret_list = []
        filters = (self.archive_extension)

        for root, directories, filenames in os.walk(self.applications_path):
            # directories = human_sort(directories)
            for filename in human_sort(filenames):
                if filename.endswith(filters):
                    file_path = os.path.join(root, filename)

                    app_archive = ApplicationArchive(file_path)  # self.get_application_metadata(file_path)
                    ret_list.append(app_archive)

        return ret_list

    def fill_table(self):
        applications = self.get_applications_list()

        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(applications))

        for index, application_archive in enumerate(applications):
            item = QTableWidgetItem(application_archive.name)
            item.setData(Qt.UserRole, index)
            self.tableWidget.setItem(index, 0, item)
            self.tableWidget.setItem(index, 1, QTableWidgetItem(application_archive.foldername))
            self.tableWidget.setItem(index, 2, QTableWidgetItem(application_archive.description))

        # Taille de cellules s'adaptant au contenu
        self.tableWidget.resizeColumnsToContents()

    def extraction_progress_update(self, percentage, filename):
        self.progressbar.setValue(int(percentage))
        self.label_2.setText(filename)

    def on_launch_button_click(self):
        current_row = self.tableWidget.currentRow()
        if current_row != -1:
            #FIXME: data marche pas, met la meme valeur à tout le monde
            #id_ = self.tableWidget.itemAt(x, current_row).data(Qt.UserRole)
            application_archive = self.applications_list[current_row]
            open_folder_after_extract = self.checkBox.isChecked()

            worker = ExtractArchiveWorker(self.tmp_folder_path, application_archive, open_folder_after_extract)
            worker.signals.current_file_progression.connect(self.extraction_progress_update)

            # Execute
            self.thread_pool.start(worker)

    def on_search_lineedit_content_changed(self):
        self.search_label = self.lineEdit.text()

    def on_open_terminal_button_click(self):
        current_row = self.tableWidget.currentRow()
        application_zip = self.applications_list[current_row]

        command = ["xdg-open"]
        subprocess.call(command)

    def clean_tmp_dir(self):
        pass

    def closeEvent(self, event):
        event.accept()


def open_file(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def human_sort(elements):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    elements.sort(key=alphanum_key)

    return elements


def main():
    __application_name__ = "Liste des outils"
    __version__ = "2021.09.23"

    app = QApplication(sys.argv)
    mainwindow = MainWindow()
    mainwindow.setWindowTitle("Liste des outils - {}".format(__version__))
    sys.exit(app.exec_())


main()
