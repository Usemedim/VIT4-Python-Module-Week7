from PyQt6.QtWidgets import QApplication, QVBoxLayout, QMainWindow, QMessageBox, QTableWidget, QTableWidgetItem, QFileDialog, QHBoxLayout, QDateEdit, QLabel, QWidget, QPushButton, QHeaderView
from PyQt6 import uic, QtCore
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
import sys
import os
import pandas as pd
import gspread
from google.oauth2 import service_account
from oauth2client.service_account import ServiceAccountCredentials
import time
import socket
from collections import defaultdict
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

UI_LOGIN = "login.ui"
UI_ADMIN_CHOICE = "admin_choices.ui"
UI_ADMIN_MENU = "admin_menu.ui"
UI_APPLICATIONS = "applications.ui"
UI_CHOICES = "choices.ui"
UI_INTERVIEW = "Interview.ui"
UI_MENTOR_MENU = "mentor_menu.ui"
CREDENTIALS_FILE = "key.json"
MAX_ATTEMPTS = 3
LOCKOUT_PERIOD = 60
TOKEN_FILE = "token.json"

class DraggableTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.mouse_pressed = False

    def mousePressEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.mouse_pressed = True
            self.start_pos = event.globalPosition().toPoint() - self.parent().frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if self.mouse_pressed:
            self.parent().move(event.globalPosition().toPoint() - self.start_pos)

    def mouseReleaseEvent(self, event):
        self.mouse_pressed = False

class LoginUI(QWidget):
    def __init__(self):
        super(LoginUI, self).__init__()
        uic.loadUi(UI_LOGIN, self)
        self.user_permission = None
        self.warning_label.clear()
        self.login_button.clicked.connect(self.login)
        self.password.returnPressed.connect(self.login)
        self.exit_button.clicked.connect(QApplication.quit)
        self.failed_attempts = defaultdict(int)
        self.blocked_ips = {}
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        self.authenticate_google_sheets()
        self.setWindowTitle("Login Menu")
        self.setGeometry(100, 100, 400, 300)
        title_bar = DraggableTitleBar(self)
        title_bar.setStyleSheet("background-color: transparent;")
        title_label = QLabel("VIT4gR3", title_bar)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                border: 3px solid red;
                border-top-left-radius: 35px;
                border-top-right-radius: 20px;
                border-bottom-left-radius: 15px;
                border-bottom-right-radius: 5px;
                background-color: #63a2ff;
            }
        """)
        title_bar_layout = QVBoxLayout(title_bar)
        title_bar_layout.addWidget(title_label)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.addWidget(title_bar)
        layout.addWidget(QLabel("Deneme"))
        self.title_bar = title_bar

    def get_credentials(self):
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE)
        return creds

    def build_service(self, api_name, version, scopes):
        creds = self.get_credentials()
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('crm.json', scopes)
                creds = flow.run_local_server(port=0)
            with open(TOKEN_FILE, 'w') as token:
                token.write(creds.to_json())
        return build(api_name, version, credentials=creds)

    def authenticate_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open("Kullanicilar")
            worksheet = spreadsheet.get_worksheet(0)
            self.all_values = worksheet.get_all_values()
            del self.all_values[0]
        except Exception as e:
            QMessageBox.critical(None, "Error", f"An error occurred while accessing Google Sheets: {str(e)}", QMessageBox.StandardButton.Ok)
            sys.exit(1)

    def validate_login(self, username, password):
        for row in self.all_values:
            user, passw, permission = row[:3]
            if username == user and password == passw:
                self.user_permission = permission
                return permission
        return None

    def login(self):
        username = self.username.text()
        password = self.password.text()
        ip_address = self.get_ip_address()
        self.menu = None
        if ip_address in self.blocked_ips:
            remaining_time = self.blocked_ips[ip_address] - time.time()
            if remaining_time > 0:
                self.warning_label.setStyleSheet("color: red")
                self.warning_label.setText(f'IP address {ip_address} is blocked! Try again after {remaining_time:.0f} seconds.')
                return
            else:
                del self.blocked_ips[ip_address]
        if self.failed_attempts[ip_address] >= MAX_ATTEMPTS:
            self.blocked_ips[ip_address] = time.time() + LOCKOUT_PERIOD
            self.warning_label.setStyleSheet("color: red")
            self.warning_label.setText(f'IP address {ip_address} is blocked! Try again after {LOCKOUT_PERIOD} seconds.')
            return
        permission = self.validate_login(username, password)
        if permission:
            if permission == "admin":
                self.menu = AdminChoicesMenu()
            else:
                self.menu = ChoicesMenu()
            self.menu.show()
            self.hide()
            self.username.clear()
            self.password.clear()
            self.warning_label.clear()
        else:
            self.username.clear()
            self.password.clear()
            self.failed_attempts[ip_address] += 1
            remaining_attempts = MAX_ATTEMPTS - self.failed_attempts[ip_address]
            if remaining_attempts > 0:
                self.warning_label.setStyleSheet("color: red")
                self.warning_label.setText(f'Inloggen mislukt! Onjuiste gebruikersnaam of wachtwoord! Resterende pogingen: {remaining_attempts}')
            else:
                self.blocked_ips[ip_address] = time.time() + LOCKOUT_PERIOD
                self.warning_label.setStyleSheet("color: red")
                self.warning_label.setText(f'IP-adres {ip_address} is geblokkeerd! Probeer het opnieuw over {LOCKOUT_PERIOD} seconden.')

                
    def get_ip_address(self):
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address

class AdminChoicesMenu(QMainWindow):
    def __init__(self):
        super(AdminChoicesMenu, self).__init__()
        uic.loadUi(UI_ADMIN_CHOICE, self)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.applications.clicked.connect(self.open_applications_menu)
        self.mentor_interviews.clicked.connect(self.open_mentor_menu)
        self.interviews.clicked.connect(self.open_interview_menu)
        self.admin_menu.clicked.connect(self.open_admin_menu)
        self.exit_button.clicked.connect(QApplication.quit)
        self.return_button.clicked.connect(self.return_to_login)
        self.shortcut_escape.activated.connect(self.return_to_login)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        title_bar = DraggableTitleBar(self)
        title_label = QLabel("Admin Choices", title_bar)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("border: 3px solid red;"
                                "border-top-left-radius: 35px;"
                                "border-top-right-radius: 20px;"
                                "border-bottom-left-radius: 15px;"
                                "border-bottom-right-radius: 5px;"
                                "background-color: #63a2ff;")
        title_bar_layout = QVBoxLayout(title_bar)
        title_bar_layout.addWidget(title_label)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.addWidget(title_bar)
        layout.addWidget(QLabel("Content goes here"))
        self.title_bar = title_bar
        
    def open_applications_menu(self):
        applications_menu.show()
        self.hide()

    def open_mentor_menu(self):
        mentor_menu.show()
        self.hide()

    def open_interview_menu(self):
        interview_menu.show()
        self.hide()

    def open_admin_menu(self):
        admin_menu.show()
        self.hide()

    def return_to_login(self):
        login_ui.show()
        self.hide()

class ApplicationsMenu(QMainWindow):
    def __init__(self):
        super(ApplicationsMenu, self).__init__()
        uic.loadUi(UI_APPLICATIONS, self)
        self.setup_ui_connections()
        self.selected_excel_file = "Basvurular"
        self.authenticate_google_sheets()
        self.setup_table()

    def setup_ui_connections(self):
        self.exit_button.clicked.connect(QApplication.quit)
        self.return_button.clicked.connect(self.return_to_menu)
        self.search_button.clicked.connect(self.filter_table)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.return_to_menu)
        self.all_applications_button.clicked.connect(self.show_all_applications)
        self.repeated_application_button.clicked.connect(self.show_repeated_applications)
        self.filter_applications_button.clicked.connect(self.show_filtered_applications)
        self.previous_vit_button.clicked.connect(self.show_previous_applications)
        self.assigned_mentors_button.clicked.connect(self.show_assigned_mentors)
        self.unassigned_mentors_button.clicked.connect(self.show_unassigned_mentors)
        self.search_text_2.returnPressed.connect(self.filter_table)
        self.search_text.returnPressed.connect(self.filter_table)
        self.export_to_excel_button.clicked.connect(self.export_to_excel)
        self.search_text.textChanged.connect(self.filter_table)
        self.search_text_2.textChanged.connect(self.filter_table)

    def setup_table(self):
        self.tableWidget.setColumnCount(7)
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

    def authenticate_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            gc = gspread.authorize(credentials)
            self.load_spreadsheets(gc)
            self.all_values = self.all_values[1:]
            self.load_data_to_table(self.all_values)
            self.all_values_vit1 = self.get_sheet_values(gc, 'VIT1', 0)[1:]
            self.all_values_vit2 = self.get_sheet_values(gc, 'VIT2', 0)[1:]
        except Exception as e:
            self.show_error_message(f"An error occurred while accessing Google Sheets: {str(e)}")

    def load_spreadsheets(self, gc):
        self.all_values = self.get_sheet_values(gc, "Basvurular", 0)

    def get_sheet_values(self, gc, sheet_name, worksheet_index):
        spreadsheet = gc.open(sheet_name)
        worksheet = spreadsheet.get_worksheet(worksheet_index)
        return worksheet.get_all_values()

    def show_repeated_applications(self):
        repeated_names = self.find_repeated_applications()
        if repeated_names:
            repeated_data = [app for app in self.all_values if app[1] in repeated_names]
            repeated_data += [app for app in self.all_values_vit1 if app[1] in repeated_names]
            repeated_data += [app for app in self.all_values_vit2 if app[1] in repeated_names]
            self.load_data_to_table(repeated_data)
        else:
            self.show_info_message("No repeated applications found.", "Repeated Applications")

    def find_repeated_applications(self):
        all_names = [app[1] for app in self.all_values]
        all_names += [app[1] for app in self.all_values_vit1]
        all_names += [app[1] for app in self.all_values_vit2]
        name_counts = {}
        repeated_names = []
        for name in all_names:
            name_counts[name] = name_counts.get(name, 0) + 1
            if name_counts[name] == 2:
                repeated_names.append(name)
        return repeated_names

    def show_filtered_applications(self):
        unique_names = set()
        filtered_data = []
        for row_data in self.all_values:
            name = row_data[1]
            if name not in unique_names:
                unique_names.add(name)
                filtered_data.append(row_data)
        self.load_data_to_table(filtered_data)

    def show_previous_applications(self):
        all_previous_applications = self.all_values_vit1 + self.all_values_vit2
        self.load_data_to_table(all_previous_applications)

    def filter_table(self):
        search_text = self.search_text_2.text().strip().lower()
        search_text_name = self.search_text.text().strip().lower()
        if not search_text and not search_text_name:
            self.load_data_to_table(self.all_values)
            return
        filtered_data = []
        for row_data in self.all_values:
            if (search_text and any(search_text in cell_data.lower() for cell_data in row_data)) or \
               (search_text_name and search_text_name in row_data[1].lower()):
                filtered_data.append(row_data)
        self.load_data_to_table(filtered_data)

    def show_all_applications(self):
        self.load_data_to_table(self.all_values)

    def show_assigned_mentors(self):
        filtered_data = [row_data for row_data in self.all_values if row_data[20].strip().lower() == 'ok']
        self.load_data_to_table(filtered_data)

    def show_unassigned_mentors(self):
        filtered_data = [row_data for row_data in self.all_values if row_data[20].strip().lower() != 'ok']
        self.load_data_to_table(filtered_data)

    def load_data_to_table(self, data):
        self.tableWidget.setRowCount(len(data))
        for row_index, row_data in enumerate(data):
            for column_index, cell_data in enumerate(row_data):
                item = QTableWidgetItem(str(cell_data))
                self.tableWidget.setItem(row_index, column_index, item)

    def return_to_menu(self):
        if login_ui.user_permission == "admin":
            admin_choice_menu.show()
        else:
            choices_menu.show()
        self.hide()

    def show_error_message(self, message):
        QMessageBox.critical(None, "jammer, Error", message, QMessageBox.StandardButton.Ok)
        sys.exit(1)

    def show_info_message(self, message, title):
        QMessageBox.information(self, title, message)

    def export_to_excel(self):
        row_count = self.tableWidget.rowCount()
        column_count = self.tableWidget.columnCount()
        data = []
        for row in range(row_count):
            row_data = []
            for column in range(column_count):
                item = self.tableWidget.item(row, column)
                row_data.append(item.text() if item else "")
            data.append(row_data)
        df = pd.DataFrame(data, columns=[self.tableWidget.horizontalHeaderItem(i).text() for i in range(column_count)])
        file_dialog = QFileDialog()
        options = file_dialog.options()
        file_path, _ = file_dialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx);;All Files (*)", options=options)
        if file_path:
            df.to_excel(file_path, index=False)
            self.show_info_message("Data successfully exported to Excel.", "Export to Excel")


class ChoicesMenu(QMainWindow):
    def __init__(self):
        super(ChoicesMenu, self).__init__()
        uic.loadUi(UI_CHOICES, self)
        self.applications.clicked.connect(self.open_applications_menu)
        self.mentor_interview.clicked.connect(self.open_mentor_menu)
        self.interview.clicked.connect(self.open_interview_menu)
        self.exit_button.clicked.connect(QApplication.instance().quit)
        self.return_button.clicked.connect(self.return_to_login)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.return_to_login)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        title_bar = DraggableTitleBar(self)
        title_label = QLabel("Choices Menu", title_bar)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("border: 3px solid red;"
                                "border-top-left-radius: 35px;"
                                "border-top-right-radius: 20px;"
                                "border-bottom-left-radius: 15px;"
                                "border-bottom-right-radius: 5px;"
                                "background-color: #63a2ff;")
        title_bar_layout = QVBoxLayout(title_bar)
        title_bar_layout.addWidget(title_label)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        layout = QVBoxLayout(self)
        layout.addWidget(title_bar)
        layout.addWidget(QLabel("Content goes here"))
        self.title_bar = title_bar

    def open_applications_menu(self):
        applications_menu.show()
        self.hide()

    def open_mentor_menu(self):
        mentor_menu.show()
        self.hide()

    def open_interview_menu(self):
        interview_menu.show()
        self.hide()

    def return_to_login(self):
        login_ui.show()
        self.hide()

class InterviewMenu(QMainWindow):
    def __init__(self):
        super(InterviewMenu, self).__init__()
        uic.loadUi(UI_INTERVIEW, self)
        self.exit_button.clicked.connect(QApplication.quit)
        self.return_button.clicked.connect(self.return_to_menu)
        self.search_button.clicked.connect(self.search_interviews)
        self.search_line.textChanged.connect(self.search_interviews)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.return_to_menu)
        self.assigned.clicked.connect(self.show_assigned_projects)
        self.received.clicked.connect(self.show_received_projects)
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.all_values = []
        self.authenticate_google_sheets()

    def authenticate_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open("Mulakatlar")
            worksheet = spreadsheet.get_worksheet(0)
            self.all_values = worksheet.get_all_values()
            del self.all_values[0]
        except Exception as e:
            QMessageBox.critical(None, "Error", f"An error occurred while accessing Google Sheets: {str(e)}", QMessageBox.StandardButton.Ok)
            sys.exit(1)

    def search_interviews(self):
        search_query = self.search_line.text().strip().lower()
        filtered_rows = [row for row in self.all_values if any(search_query in cell.lower() for cell in row)]
        self.update_table(filtered_rows)

    def show_assigned_projects(self):
        try:
            assigned_projects = [row for row in self.all_values if len(row) > 1 and row[1].strip()]
            if not assigned_projects:
                QMessageBox.information(self, "Info", "No assigned projects found.", QMessageBox.StandardButton.Ok)
            self.update_table(assigned_projects)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while filtering assigned projects: {str(e)}", QMessageBox.StandardButton.Ok)

    def show_received_projects(self):
        try:
            received_projects = [row for row in self.all_values if len(row) > 2 and row[2].strip()]
            if not received_projects:
                QMessageBox.information(self, "Info", "No received projects found.", QMessageBox.StandardButton.Ok)
            self.update_table(received_projects)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while filtering received projects: {str(e)}", QMessageBox.StandardButton.Ok)

    def update_table(self, rows):
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)
        self.tableWidget.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            for col_index, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                self.tableWidget.setItem(row_index, col_index, item)

    def return_to_menu(self):
        if login_ui.user_permission == "admin":
            admin_choice_menu.show()
        else:
            choices_menu.show()
        self.hide()

class MentorMenu(QMainWindow):
    def __init__(self):
        super(MentorMenu, self).__init__()
        uic.loadUi(UI_MENTOR_MENU, self)
        self.exit_button.clicked.connect(QApplication.quit)
        self.return_button.clicked.connect(self.return_to_menu)
        self.search_button.clicked.connect(self.search_candidates)
        self.search_line.textChanged.connect(self.search_candidates)
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.return_to_menu)
        self.all_interviews.clicked.connect(self.list_all_interviews)
        self.cokluSecenekKutusu.currentIndexChanged.connect(self.filter_by_combobox_selection)
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.save_button.clicked.connect(self.save_changes)
        self.all_values = []
        self.authenticate_google_sheets()

    def authenticate_google_sheets(self):
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open('Mentor')
            worksheet = spreadsheet.get_worksheet(0)
            self.all_values = worksheet.get_all_values()
            del self.all_values[0]
            f_column_values = [row[5].strip() for row in self.all_values if len(row) > 5]
            f_column_values = sorted(set(f_column_values))
            self.cokluSecenekKutusu.addItem("")
            for value in f_column_values:
                self.cokluSecenekKutusu.addItem(value)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while accessing Google Sheets: {str(e)}", QMessageBox.StandardButton.Ok)
            sys.exit(1)

    def search_candidates(self):
        search_query = self.search_line.text().strip().lower()
        if not search_query:
            return
        filtered_rows = [row for row in self.all_values if len(row) > 2 and search_query in row[2].lower()]
        self.update_table(filtered_rows)

    def list_all_interviews(self):
        self.update_table(self.all_values)

    def update_table(self, rows):
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)
        self.tableWidget.setRowCount(len(rows))
        self.tableWidget.setColumnCount(len(self.all_values[0]))
        for row_index, row_data in enumerate(rows):
            for col_index, cell_data in enumerate(row_data):
                item = QTableWidgetItem(cell_data)
                self.tableWidget.setItem(row_index, col_index, item)

    def update_selected_row(self):
        selected_row = self.tableWidget.currentRow()
        selected_column = self.tableWidget.currentColumn()
        combo_text = self.cokluSecenekKutusu.currentText()
        if selected_row >= 0 and selected_column >= 0 and combo_text:
            self.tableWidget.setItem(selected_row, selected_column, QTableWidgetItem(combo_text))

    def filter_by_combobox_selection(self):
        combo_text = self.cokluSecenekKutusu.currentText().strip().lower()
        if not combo_text:
            self.update_table(self.all_values)
            return
        filtered_rows = [row for row in self.all_values if row[5].strip().lower() == combo_text]
        self.update_table(filtered_rows)

    def save_changes(self):
        file_url = "https://docs.google.com/spreadsheets/d/14ejScXyN41mATnmZBcHsMOl83HHbb0W2Lc-HeT4TcXs"
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            gc = gspread.authorize(credentials)
            spreadsheet = gc.open_by_url(file_url)
            worksheet = spreadsheet.get_worksheet(0)
            data = []
            self.all_values = []
            for row in range(self.tableWidget.rowCount()):
                row_data = []
                for col in range(self.tableWidget.columnCount()):
                    item = self.tableWidget.item(row, col)
                    cell_value = item.text() if item is not None else ''
                    row_data.append(cell_value)
                data.append(row_data)
                self.all_values.append(row_data)

            worksheet.update('A1', data)
            QMessageBox.information(self, "Success", "Changes saved successfully.")
            self.update_table(self.all_values)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"An error occurred: {str(e)}")

    def list_all_interviews(self):
        if not self.all_values:
            try:
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
                gc = gspread.authorize(credentials)
                spreadsheet = gc.open('Mentor')
                worksheet = spreadsheet.get_worksheet(0)
                self.all_values = worksheet.get_all_values()
                del self.all_values[0]
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred while accessing Google Sheets: {str(e)}", QMessageBox.StandardButton.Ok)
        self.update_table(self.all_values)

    def return_to_menu(self):
        if login_ui.user_permission == "admin":
            admin_choice_menu.show()
        else:
            choices_menu.show()
        self.hide()

class AdminMenu(QMainWindow):
    def __init__(self):
        super(AdminMenu, self).__init__()
        uic.loadUi('admin_menu.ui', self)
        self.setWindowTitle("Admin Menu")
        self.tableWidget = self.findChild(QTableWidget, "tableWidget")
        self.check_activity.clicked.connect(self.show_event_registration_records)
        self.send_mail_button.clicked.connect(self.handle_send_email)
        self.return_button.clicked.connect(self.back_to_admin_choice)
        self.exit_button.clicked.connect(QApplication.quit)
        self.startDateEdit = self.findChild(QDateEdit, "dateEdit")
        self.endDateEdit = self.findChild(QDateEdit, "dateEdit_2")
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.back_to_admin_choice)
        creds = service_account.Credentials.from_service_account_file(
            'crm.json',
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        self.calendar_service = build('calendar', 'v3', credentials=creds)
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)

    def show_event_registration_records(self):
        try:
            time_min = self.startDateEdit.date().toString(QtCore.Qt.DateFormat.ISODate) + "T00:00:00Z"
            time_max = self.endDateEdit.date().toString(QtCore.Qt.DateFormat.ISODate) + "T23:59:59Z"
            events_result = self.calendar_service.events().list(
                calendarId="werherevit@gmail.com",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=1000,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            events = events_result.get('items', [])
            if not events:
                QMessageBox.warning(self, "Warning", "No events found!", QMessageBox.StandardButton.Ok)
                return
            self.tableWidget.setRowCount(0)
            for event in events:
                event_name = event.get("summary", "No Title")
                start_time = event['start'].get('dateTime', event['start'].get('date'))
                organizer_email = event.get('organizer', {}).get('email', 'No Email')
                attendees = event.get('attendees', [])
                participant_emails = []
                for attendee in attendees:
                    email = attendee.get('email')
                    if email != organizer_email:
                        participant_emails.append(email)
                if not participant_emails:
                    participant_emails.append(organizer_email)
                participants_str = ", ".join(participant_emails)
                rowPosition = self.tableWidget.rowCount()
                self.tableWidget.insertRow(rowPosition)
                self.tableWidget.setItem(rowPosition, 0, QTableWidgetItem(event_name))
                self.tableWidget.setItem(rowPosition, 1, QTableWidgetItem(start_time))
                self.tableWidget.setItem(rowPosition, 2, QTableWidgetItem(participants_str))
                self.tableWidget.setItem(rowPosition, 3, QTableWidgetItem(organizer_email))
                self.add_email_button(rowPosition, event_name, start_time, participants_str, participant_emails)
            header = self.tableWidget.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(0, 200)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {e}", QMessageBox.StandardButton.Ok)

    def add_email_button(self, row, event_name, start_time, participants_str, recipients):
        send_button = QPushButton('Send Email')
        send_button.clicked.connect(lambda: self.send_email(event_name, start_time, participants_str, recipients))
        self.tableWidget.setCellWidget(row, 4, send_button)

    def handle_send_email(self):
        current_row = self.tableWidget.currentRow()
        if current_row >= 0:
            event_name = self.tableWidget.item(current_row, 0).text()
            start_time = self.tableWidget.item(current_row, 1).text()
            participants_str = self.tableWidget.item(current_row, 2).text()
            recipients = participants_str.split(", ")
            self.send_email(event_name, start_time, participants_str, recipients)
        else:
            QMessageBox.warning(self, "Warning", "Please select an event to send email.", QMessageBox.StandardButton.Ok)

    def send_email(self, event_name, start_time, participants_str, recipients):
        # Diger email patlarsa buradan yururuz-Yedek
        # sender_email = "ecitayyar@gmail.com"
        # smtp_server = "smtp.gmail.com"
        # smtp_port = 587
        # smtp_username = "ecitayyar@gmail.com"
        # smtp_password = "dmlcyaewmozzcsdg"
        sender_email = "werherevit@gmail.com"
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = "werherevit@gmail.com"
        smtp_password = "gnwjcrfknhazikba"
        subject = f"VIT4gR3-CRM Project, Event Invitation: {event_name}"
        message_body = f"Dear all,\n\nYou are invited to attend the event '{event_name}' starting at {start_time}.\n\nParticipants: {participants_str}"
        try:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
        except Exception as e:
            QMessageBox.critical(self, "SMTP Connection Error", f"Error during connection/login: {e}")
            return
        sent_recipients = []
        failed_recipients = []
        for receiver_email in recipients:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = receiver_email
            msg['Subject'] = subject
            msg.attach(MIMEText(message_body, 'plain'))
            try:
                server.send_message(msg)
                sent_recipients.append(receiver_email)
            except Exception as e:
                failed_recipients.append(receiver_email)
                error_message = f'Error sending email to {receiver_email}: {e}'
                QMessageBox.warning(self, "Email Sending Error", error_message)
        server.quit()
        if sent_recipients:
            sent_message = "Emails sent successfully to:\n" + "\n".join(sent_recipients)
            QMessageBox.information(self, "Email Status", sent_message)
        if failed_recipients:
            failed_message = "Failed to send emails to:\n" + "\n".join(failed_recipients)
            QMessageBox.warning(self, "Email Status", failed_message)

    def back_to_admin_choice(self):
        admin_choice_menu.show()
        self.hide()

app = QApplication(sys.argv)
login_ui = LoginUI()
applications_menu = ApplicationsMenu()
choices_menu = ChoicesMenu()
admin_choice_menu = AdminChoicesMenu()
interview_menu = InterviewMenu()
mentor_menu = MentorMenu()
admin_menu = AdminMenu()
login_ui.show()
sys.exit(app.exec())