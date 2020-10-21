#!/bin/env python3

from PyQt5.QtWidgets import QApplication
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import  QMainWindow, QMessageBox, QTableWidgetItem

import sys
import os
import shutil
import zipfile
import platform
import subprocess
import configparser
import re

# Date de création: 2020.08.21
# Date de modification: 2020.08.25

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()

        # Config
        config = configparser.ConfigParser()
        config.read("config.ini")

        self.applications_path = config["config"]["root"]
        if not os.path.exists(self.applications_path):
            msg = "Le dossier <b>{}</b> n'existe pas.".format(self.applications_path)
            qmessagbox = QMessageBox(text=msg)
            qmessagbox.setWindowTitle("Erreur")
            #qmessagbox.setText("Erreur problème d'extraction")
            qmessagbox.exec()

        self.tmp_folder_path = config["config"]["tmp"]
        self.archive_extension = config["config"]["archive_extension"]

        self.init_ui()
        self.init_events()

        self.applications_list = self.get_applications_list()

        self.fill_table()
        self.show()

    def init_ui(self):
        loadUi(os.path.join(os.path.dirname(__file__), "gui.ui"), self)

    def init_events(self):
        self.pushButton.clicked.connect(self.on_launch_button_click)
        self.lineEdit.textChanged.connect(self.on_search_lineEdit_content_changed)

    def get_applications_list(self):
        ret_list = []
        filters = (self.archive_extension)

        for root, directories, filenames in os.walk(self.applications_path):
            directories = human_sort(directories)
            for filename in human_sort(filenames):
                if filename.endswith(filters):
                    file_path = os.path.join(root, filename)
                    ret_list.append(file_path)

        return ret_list

    def fill_table(self):
        applications = self.get_applications_list()

        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(len(applications))
        
        for index, application in enumerate(applications):
                application_name = os.path.basename(application).strip(self.archive_extension)
                # On affiche le chemin et on supprime lechemin complet
                application_folder = application.replace("\\", "/")
                foldername = os.path.basename(os.path.dirname(application))

                self.tableWidget.setItem(index, 0, QTableWidgetItem(application_name))
                self.tableWidget.setItem(index, 1, QTableWidgetItem(foldername))
                #self.tableWidget.setItem(id, 2, QTableWidgetItem(planningEpisodeId))


        # Taille de cellules s'adaptant au contenu
        self.tableWidget.resizeColumnsToContents()

    def on_launch_button_click(self):
        current_row = self.tableWidget.currentRow()
        if current_row != -1:
            application_zip = self.applications_list[current_row]

            application_tmp_dir = self.extract(application_zip)
            if self.checkBox.isChecked() and application_tmp_dir:
                open_file(application_tmp_dir)

    def on_search_lineEdit_content_changed(self):
        print(self.lineEdit.text())
        text = self.lineEdit.text()

    def on_open_terminal_button_click(self):
        current_row = self.tableWidget.currentRow()
        application_zip = self.applications_list[current_row]

        command = ["xdg-open"]
        subprocess.call(command)

    def extract(self, archive_file):
        application_name = application_name = os.path.basename(archive_file).strip(self.archive_extension)
        application_tmp_dir = os.path.join(self.tmp_folder_path, application_name)

        # Création du dossier de l'application
        if os.path.exists(application_tmp_dir):
            shutil.rmtree(application_tmp_dir) 

        else:
            os.makedirs(application_tmp_dir)

        # Extraction du dossier
        try:
            with zipfile.ZipFile(archive_file, "r") as archive_file:
                archive_file.extractall(application_tmp_dir)

            return application_tmp_dir

        except(IOError, zipfile.BadZipfile) as e:
            msgbox = QMessageBox()
            msgbox.setWindowTitle("Erreur problème d'extraction")
            msgbox.setText("Erreur problème d'extraction")
            msgbox.setDetailedText(str(e))
            msgbox.setIcon(QMessageBox.Critical)
            msgbox.exec()

            return None

def open_file(path):
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])

def human_sort(elements):
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda key: [ convert(c) for c in re.split('([0-9]+)', key) ]
    elements.sort(key=alphanum_key)

    return elements

def main():
    __application_name__ = "Liste des outils"
    __version__ = "0.2"

    application = QApplication(sys.argv)
    mainwindow = MainWindow()
    mainwindow.setWindowTitle ("Liste des outils - {}".format(__version__))
    sys.exit(application.exec_())

main()