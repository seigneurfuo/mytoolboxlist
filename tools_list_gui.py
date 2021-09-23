#!/bin/env python3

# Date de création: 2020.08.21
# Date de modification: 2021.08.05

import sys
import os
import shutil
import zipfile
import platform
import subprocess
import configparser
import re

from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import QThreadPool, QRunnable, pyqtSlot, Qt, QObject, pyqtSignal


class ExtractArchiveWorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    file_progression: int progress complete,from 0-100
    '''

    current_file_progression = pyqtSignal(int) # pourcentage actuel

class ExtractArchiveWorker(QRunnable):
    def __init__(self, tmp_folder_path, archive_extension, application_object, open_folder_after_extract):
        super(ExtractArchiveWorker, self).__init__()
        self.signals = ExtractArchiveWorkerSignals()

        self.tmp_folder_path = tmp_folder_path
        self.archive_extension = archive_extension
        self.application_object = application_object
        self.open_folder_after_extract = open_folder_after_extract

    @pyqtSlot()
    def run(self):
        application_tmp_dir = os.path.join(self.tmp_folder_path, self.application_object['name'])
        # Création du dossier de l'application
        if os.path.exists(application_tmp_dir):
            shutil.rmtree(application_tmp_dir)

        else:
            os.makedirs(application_tmp_dir)

        # Extraction du dossier (https://usefulscripting.network/python/extracting-files-with-progress/)
        try:
            with zipfile.ZipFile(self.application_object['filepath'], "r") as archive_file:
                total_elements = len(archive_file.namelist())

                for index, filename in enumerate(archive_file.namelist()):
                    percentage = int(index * (100 / total_elements))

                    msg = "Extraction fichier {} sur {} ({}%) => {}".format(index + 1, total_elements, percentage, filename)
                    print(msg)

                    archive_file.extract(member=filename, path=application_tmp_dir)

                    self.signals.current_file_progression.emit(percentage)

                print("Terminé !")

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
            directories = human_sort(directories)
            for filename in human_sort(filenames):
                if filename.endswith(filters):
                    file_path = os.path.join(root, filename)

                    application = self.get_application_metadata(file_path)
                    ret_list.append(application)

        return ret_list

    def get_application_metadata(self, file_path):
        foldername = os.path.basename(os.path.dirname(file_path))
        application_name = os.path.basename(file_path).removesuffix(self.archive_extension) # Spécifique Python 3.9 !
        application = \
        {
            "filepath": file_path,
            "foldername": foldername,
            "name": application_name,
            "description": "",
            "os": ""
        }

        # Si on à des fichier de métadonnées on le charge ici
        metadata_filepath = file_path.removesuffix(self.archive_extension) + self.metadata_file_extension  # Spécifique Python 3.9 !
        if os.path.isfile(metadata_filepath):
            try:
                metadata = configparser.ConfigParser()
                metadata.read(metadata_filepath)
                # Spécifique Python 3.9 !

                application |= \
                {
                    #"name":         metadata["software"]["name"],
                    "description":  metadata["software"]["description"],
                    "os":           metadata["software"]["os"]
                }

            except:
                pass

        return application

    def fill_table(self):
        applications = self.get_applications_list()

        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(applications))


        for index, application_object in enumerate(applications):
            item = QTableWidgetItem(application_object["name"])
            item.setData(Qt.UserRole, application_object)
            self.tableWidget.setItem(index, 0, item)
            self.tableWidget.setItem(index, 1, QTableWidgetItem(application_object["foldername"]))
            self.tableWidget.setItem(index, 2, QTableWidgetItem(application_object["description"]))

        # Taille de cellules s'adaptant au contenu
        self.tableWidget.resizeColumnsToContents()

    def on_launch_button_click(self):
        current_row = self.tableWidget.currentRow()
        if current_row != -1:
            open_folder_after_extract = self.checkBox.isChecked()
            application_object = self.tableWidget.currentItem().data(Qt.UserRole)
            worker = ExtractArchiveWorker(self.tmp_folder_path, self.archive_extension, application_object, open_folder_after_extract)
            #worker.signals.current_file_progression.connect(self.current_file_progression)

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
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def human_sort(elements):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    elements.sort(key=alphanum_key)

    return elements


def main():
    __application_name__ = "Liste des outils"
    __version__ = "2021.09.08"

    app = QApplication(sys.argv)
    mainwindow = MainWindow()
    mainwindow.setWindowTitle("Liste des outils - {}".format(__version__))
    sys.exit(app.exec_())


main()
