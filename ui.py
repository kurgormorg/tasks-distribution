import sys
import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, 
                            QComboBox, QTextEdit, QGroupBox, QFormLayout, QDialog, QDateTimeEdit, 
                            QHeaderView, QStackedWidget, QSplitter, QFrame)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QIcon, QFont, QColor

# Импортируем класс TaskManager из main.py
from main import TaskManager

class LoginWindow(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Вход в систему управления задачами')
        self.setMinimumSize(400, 250)
        
        layout = QVBoxLayout()
        
        # Заголовок
        title_label = QLabel('Система управления задачами')
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        layout.addSpacing(20)
        
        # Поля для ввода
        form_layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText('Введите имя пользователя')
        form_layout.addRow('Пользователь:', self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText('Введите пароль')
        self.password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow('Пароль:', self.password_edit)
        
        layout.addLayout(form_layout)
        layout.addSpacing(20)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        
        self.login_button = QPushButton('Войти')
        self.login_button.clicked.connect(self.login)
        buttons_layout.addWidget(self.login_button)
        
        self.register_button = QPushButton('Регистрация')
        self.register_button.clicked.connect(self.open_register_dialog)
        buttons_layout.addWidget(self.register_button)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
    
    def login(self):
        username = self.username_edit.text()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, 'Ошибка', 'Заполните все поля')
            return
        
        result = self.task_manager.login(username, password)
        if result:
            self.parent().open_main_window()
        else:
            QMessageBox.warning(self, 'Ошибка', 'Неверное имя пользователя или пароль')
    
    def open_register_dialog(self):
        dialog = RegisterDialog(self.task_manager)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            QMessageBox.information(self, 'Успех', 'Пользователь успешно зарегистрирован')


class RegisterDialog(QDialog):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Регистрация нового пользователя')
        self.setMinimumSize(400, 250)
        
        layout = QFormLayout()
        
        self.username_edit = QLineEdit()
        layout.addRow('Имя пользователя:', self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout.addRow('Пароль:', self.password_edit)
        
        self.fullname_edit = QLineEdit()
        layout.addRow('Полное имя:', self.fullname_edit)
        
        self.email_edit = QLineEdit()
        layout.addRow('Email:', self.email_edit)
        
        # Чекбокс для админа
        self.admin_checkbox = QComboBox()
        self.admin_checkbox.addItems(['Обычный пользователь', 'Администратор'])
        layout.addRow('Тип пользователя:', self.admin_checkbox)
        
        buttons_layout = QHBoxLayout()
        self.register_btn = QPushButton('Зарегистрировать')
        self.register_btn.clicked.connect(self.register_user)
        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.register_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addRow('', buttons_layout)
        self.setLayout(layout)
    
    def register_user(self):
        username = self.username_edit.text()
        password = self.password_edit.text()
        fullname = self.fullname_edit.text()
        email = self.email_edit.text()
        is_admin = self.admin_checkbox.currentIndex() == 1
        
        if not username or not password or not fullname:
            QMessageBox.warning(self, 'Ошибка', 'Заполните обязательные поля')
            return
        
        result = self.task_manager.register_user(
            username=username,
            password=password,
            full_name=fullname,
            is_admin=is_admin,
            email=email if email else None
        )
        
        if isinstance(result, str) and not result.startswith('Ошибка'):
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', str(result))


class TasksTab(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Фильтры
        filters_layout = QHBoxLayout()
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(['Все статусы', 'новая', 'в работе', 'выполнена', 'отменена'])
        self.status_filter.currentIndexChanged.connect(self.load_tasks)
        filters_layout.addWidget(QLabel('Статус:'))
        filters_layout.addWidget(self.status_filter)
        
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self.load_tasks)
        filters_layout.addWidget(self.refresh_btn)
        
        self.create_task_btn = QPushButton('Создать задачу')
        self.create_task_btn.clicked.connect(self.open_create_task_dialog)
        filters_layout.addWidget(self.create_task_btn)
        
        filters_layout.addStretch()
        layout.addLayout(filters_layout)
        
        # Таблица задач
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(7)
        self.tasks_table.setHorizontalHeaderLabels(['ID', 'Название', 'Статус', 'Приоритет', 'Создана', 'Дедлайн', 'Исполнитель'])
        self.tasks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.tasks_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tasks_table.doubleClicked.connect(self.open_task_details)
        layout.addWidget(self.tasks_table)
        
        self.setLayout(layout)
        self.load_tasks()
    
    def load_tasks(self):
        status = None if self.status_filter.currentIndex() == 0 else self.status_filter.currentText()
        
        tasks = self.task_manager.get_user_tasks(status=status)
        
        if isinstance(tasks, list):
            self.tasks_table.setRowCount(0)  # Очистка таблицы
            
            for row, task in enumerate(tasks):
                self.tasks_table.insertRow(row)
                self.tasks_table.setItem(row, 0, QTableWidgetItem(task['id']))
                self.tasks_table.setItem(row, 1, QTableWidgetItem(task['title']))
                self.tasks_table.setItem(row, 2, QTableWidgetItem(task['status']))
                self.tasks_table.setItem(row, 3, QTableWidgetItem(task['priority']))
                
                # Форматирование даты
                created_date = task['created_at'].strftime('%d.%m.%Y %H:%M')
                self.tasks_table.setItem(row, 4, QTableWidgetItem(created_date))
                
                deadline = '-'
                if task['deadline']:
                    deadline = task['deadline'].strftime('%d.%m.%Y %H:%M')
                self.tasks_table.setItem(row, 5, QTableWidgetItem(deadline))
                
                self.tasks_table.setItem(row, 6, QTableWidgetItem(task.get('assignee_name', '-')))
                
                # Цветовая индикация статуса
                if task['status'] == 'новая':
                    self.tasks_table.item(row, 2).setBackground(QColor(173, 216, 230))  # LightBlue
                elif task['status'] == 'в работе':
                    self.tasks_table.item(row, 2).setBackground(QColor(255, 255, 0))  # Yellow
                elif task['status'] == 'выполнена':
                    self.tasks_table.item(row, 2).setBackground(QColor(144, 238, 144))  # LightGreen
                elif task['status'] == 'отменена':
                    self.tasks_table.item(row, 2).setBackground(QColor(255, 182, 193))  # LightPink
        else:
            QMessageBox.warning(self, 'Ошибка', str(tasks))
    
    def open_create_task_dialog(self):
        dialog = CreateTaskDialog(self.task_manager)
        if dialog.exec_() == QDialog.Accepted:
            self.load_tasks()
    
    def open_task_details(self):
        selected_row = self.tasks_table.currentRow()
        if selected_row >= 0:
            task_id = self.tasks_table.item(selected_row, 0).text()
            dialog = TaskDetailsDialog(self.task_manager, task_id)
            dialog.exec_()
            self.load_tasks()  # Обновляем после закрытия диалога


class CreateTaskDialog(QDialog):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Создание новой задачи')
        self.setMinimumSize(500, 400)
        
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        self.title_edit = QLineEdit()
        form_layout.addRow('Название задачи:', self.title_edit)
        
        self.desc_edit = QTextEdit()
        form_layout.addRow('Описание:', self.desc_edit)
        
        # Выбор отдела
        self.dept_combo = QComboBox()
        self.dept_combo.addItem('Не указан', None)
        # Здесь нужно загрузить список отделов
        form_layout.addRow('Отдел:', self.dept_combo)
        
        # Выбор исполнителя
        self.assignee_combo = QComboBox()
        self.assignee_combo.addItem('Не назначен', None)
        # Здесь нужно загрузить список пользователей
        form_layout.addRow('Исполнитель:', self.assignee_combo)
        
        # Приоритет
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(['обычный', 'высокий', 'низкий'])
        form_layout.addRow('Приоритет:', self.priority_combo)
        
        # Дедлайн
        self.deadline_edit = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
        self.deadline_edit.setCalendarPopup(True)
        self.deadline_check = QComboBox()
        self.deadline_check.addItems(['Без дедлайна', 'С дедлайном'])
        self.deadline_check.currentIndexChanged.connect(lambda idx: self.deadline_edit.setEnabled(idx == 1))
        self.deadline_edit.setEnabled(False)
        
        deadline_layout = QHBoxLayout()
        deadline_layout.addWidget(self.deadline_check)
        deadline_layout.addWidget(self.deadline_edit)
        form_layout.addRow('Дедлайн:', deadline_layout)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.create_btn = QPushButton('Создать')
        self.create_btn.clicked.connect(self.create_task)
        self.cancel_btn = QPushButton('Отмена')
        self.cancel_btn.clicked.connect(self.reject)
        
        buttons_layout.addWidget(self.create_btn)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
        
        # Загрузка списков
        self.load_departments()
        self.load_users()
    
    def load_departments(self):
        self.dept_combo.clear()
        self.dept_combo.addItem('Не указан', None)
        departments = self.task_manager.db.fetch_all("SELECT id, name FROM departments ORDER BY name")
        for dept in departments:
            self.dept_combo.addItem(dept["name"], dept["id"])

    def load_users(self):
        self.assignee_combo.clear()
        self.assignee_combo.addItem('Не назначен', None)
        users = self.task_manager.db.fetch_all("SELECT id, full_name FROM users ORDER BY full_name")
        for user in users:
            self.assignee_combo.addItem(user["full_name"], user["id"])
    
    def create_task(self):
        title = self.title_edit.text()
        description = self.desc_edit.toPlainText()
        
        if not title:
            QMessageBox.warning(self, 'Ошибка', 'Введите название задачи')
            return
        
        department_id = self.dept_combo.currentData()
        assigned_to = self.assignee_combo.currentData()
        priority = self.priority_combo.currentText()
        
        deadline = None
        if self.deadline_check.currentIndex() == 1:
            deadline = self.deadline_edit.dateTime().toPyDateTime()
        
        result = self.task_manager.create_task(
            title=title,
            description=description,
            department_id=department_id,
            assigned_to=assigned_to,
            deadline=deadline,
            priority=priority
        )
        
        if isinstance(result, str) and not result.startswith('Ошибка'):
            QMessageBox.information(self, 'Успех', 'Задача успешно создана')
            self.accept()
        else:
            QMessageBox.warning(self, 'Ошибка', str(result))


class TaskDetailsDialog(QDialog):
    def __init__(self, task_manager, task_id):
        super().__init__()
        self.task_manager = task_manager
        self.task_id = task_id
        self.initUI()
        self.load_task_details()
        self.load_comments()
    
    def initUI(self):
        self.setWindowTitle(f'Детали задачи')
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout()
        
        # Детали задачи
        details_group = QGroupBox('Информация о задаче')
        details_layout = QFormLayout()
        
        self.title_label = QLabel()
        details_layout.addRow('Название:', self.title_label)
        
        self.desc_label = QLabel()
        self.desc_label.setWordWrap(True)
        details_layout.addRow('Описание:', self.desc_label)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(['новая', 'в работе', 'выполнена', 'отменена'])
        self.status_combo.currentIndexChanged.connect(self.update_task_status)
        details_layout.addRow('Статус:', self.status_combo)
        
        self.priority_label = QLabel()
        details_layout.addRow('Приоритет:', self.priority_label)
        
        self.created_label = QLabel()
        details_layout.addRow('Создана:', self.created_label)
        
        self.deadline_label = QLabel()
        details_layout.addRow('Дедлайн:', self.deadline_label)
        
        self.creator_label = QLabel()
        details_layout.addRow('Создатель:', self.creator_label)
        
        self.assignee_label = QLabel()
        details_layout.addRow('Исполнитель:', self.assignee_label)
        
        details_group.setLayout(details_layout)
        layout.addWidget(details_group)
        
        # Комментарии
        comments_group = QGroupBox('Комментарии')
        comments_layout = QVBoxLayout()
        
        self.comments_area = QTextEdit()
        self.comments_area.setReadOnly(True)
        comments_layout.addWidget(self.comments_area)
        
        # Добавление комментария
        comment_input_layout = QHBoxLayout()
        self.comment_edit = QLineEdit()
        self.comment_edit.setPlaceholderText('Введите комментарий...')
        self.add_comment_btn = QPushButton('Добавить')
        self.add_comment_btn.clicked.connect(self.add_comment)
        
        comment_input_layout.addWidget(self.comment_edit)
        comment_input_layout.addWidget(self.add_comment_btn)
        comments_layout.addLayout(comment_input_layout)
        
        comments_group.setLayout(comments_layout)
        layout.addWidget(comments_group)
        
        # Кнопки
        buttons_layout = QHBoxLayout()
        self.close_btn = QPushButton('Закрыть')
        self.close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.close_btn)
        
        layout.addLayout(buttons_layout)
        self.setLayout(layout)
    
    def load_task_details(self):
        task = self.task_manager.db.fetch_one(
            """
            SELECT t.title, t.description, t.status, t.priority, t.created_at, t.deadline,
                    creator.full_name, assignee.full_name
            FROM tasks t
            LEFT JOIN users creator ON t.created_by = creator.id
            LEFT JOIN users assignee ON t.assigned_to = assignee.id
            WHERE t.id = %s
            """,
            (self.task_id,)
        )

        if task:
            self.title_label.setText(task[0])
            self.desc_label.setText(task[1])
            self.status_combo.setCurrentText(task[2])
            self.priority_label.setText(task[3])
            self.created_label.setText(task[4].strftime('%d.%m.%Y %H:%M'))
            self.deadline_label.setText(task[5].strftime('%d.%m.%Y %H:%M') if task[5] else '-')
            self.creator_label.setText(task[6])
            self.assignee_label.setText(task[7] if task[7] else '-')
        else:
            QMessageBox.warning(self, 'Ошибка', 'Не удалось загрузить информацию о задаче')
    
    def load_comments(self):
        comments = self.task_manager.get_task_comments(self.task_id)
        if isinstance(comments, list):
            comments_text = ""
            for comment in comments:
                date_str = comment['created_at'].strftime('%d.%m.%Y %H:%M')
                comments_text += f"<b>{comment['user_name']}</b> ({date_str}):<br>{comment['text']}<br><br>"
            self.comments_area.setHtml(comments_text)
        else:
            self.comments_area.setText("Ошибка загрузки комментариев")
    
    def update_task_status(self):
        status = self.status_combo.currentText()
        result = self.task_manager.update_task_status(self.task_id, status)
        if result is not True:
            QMessageBox.warning(self, 'Ошибка', str(result))
    
    def add_comment(self):
        comment_text = self.comment_edit.text()
        if not comment_text:
            return
        result = self.task_manager.add_task_comment(self.task_id, comment_text)
        if isinstance(result, str) and not result.startswith("Ошибка"):
            self.load_comments()
            self.comment_edit.clear()
        else:
            QMessageBox.warning(self, 'Ошибка', str(result))


class NotificationsTab(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Панель управления
        controls_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self.load_notifications)
        controls_layout.addWidget(self.refresh_btn)
        
        self.mark_all_read_btn = QPushButton('Отметить все как прочитанные')
        self.mark_all_read_btn.clicked.connect(self.mark_all_as_read)
        controls_layout.addWidget(self.mark_all_read_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Список уведомлений
        self.notifications_table = QTableWidget()
        self.notifications_table.setColumnCount(4)
        self.notifications_table.setHorizontalHeaderLabels(['ID', 'Сообщение', 'Дата', 'Прочитано'])
        self.notifications_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.notifications_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.notifications_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.notifications_table)
        
        self.setLayout(layout)
        self.load_notifications()
    
    def load_notifications(self):
        # В реальном приложении нужно загрузить уведомления из базы
        if self.task_manager.current_user:
            notifications = self.task_manager.notification_service.get_user_notifications(self.task_manager.current_user.id)
            
            if isinstance(notifications, list):
                self.notifications_table.setRowCount(0)  # Очистка таблицы
                
                for row, notif in enumerate(notifications):
                    self.notifications_table.insertRow(row)
                    self.notifications_table.setItem(row, 0, QTableWidgetItem(notif['id']))
                    self.notifications_table.setItem(row, 1, QTableWidgetItem(notif['message']))
                    
                    date_str = notif['created_at'].strftime('%d.%m.%Y %H:%M')
                    self.notifications_table.setItem(row, 2, QTableWidgetItem(date_str))
                    
                    read_status = 'Да' if notif['is_read'] else 'Нет'
                    self.notifications_table.setItem(row, 3, QTableWidgetItem(read_status))
                    
                    # Выделение непрочитанных уведомлений
                    if not notif['is_read']:
                        for col in range(4):
                            self.notifications_table.item(row, col).setBackground(QColor(240, 240, 255))
    
    def mark_all_as_read(self):
        if self.task_manager.current_user:
            result = self.task_manager.notification_service.mark_all_notifications_as_read(self.task_manager.current_user.id)
            if result is True:
                QMessageBox.information(self, 'Успех', 'Все уведомления отмечены как прочитанные')
                self.load_notifications()
            else:
                QMessageBox.warning(self, 'Ошибка', 'Не удалось отметить уведомления как прочитанные')


class DepartmentsTab(QWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.initUI()
        
    def initUI(self):
        layout = QVBoxLayout()
        
        # Управление отделами
        controls_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton('Обновить')
        self.refresh_btn.clicked.connect(self.load_departments)
        controls_layout.addWidget(self.refresh_btn)
        
        self.create_dept_btn = QPushButton('Создать отдел')
        self.create_dept_btn.clicked.connect(self.create_department)
        controls_layout.addWidget(self.create_dept_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Список отделов
        self.departments_table = QTableWidget()
        self.departments_table.setColumnCount(3)
        self.departments_table.setHorizontalHeaderLabels(['ID', 'Название', 'Руководитель'])
        self.departments_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.departments_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.departments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.departments_table.doubleClicked.connect(self.view_department)
        layout.addWidget(self.departments_table)
        
        self.setLayout(layout)
        
        # Загружаем список отделов после инициализации
        self.load_departments()
    
    def load_departments(self):
        # В реальном приложении нужно загрузить отделы из базы
        # Для примера используем фиктивные данные
        departments = [
            {'id': 'dept1', 'name': 'IT отдел', 'head_name': 'Иванов Иван'},
            {'id': 'dept2', 'name': 'Бухгалтерия', 'head_name': 'Петров Петр'}
        ]
        
        self.departments_table.setRowCount(0)  # Очистка таблицы
        
        for row, dept in enumerate(departments):
            self.departments_table.insertRow(row)
            self.departments_table.setItem(row, 0, QTableWidgetItem(dept['id']))
            self.departments_table.setItem(row, 1, QTableWidgetItem(dept['name']))
            self.departments_table.setItem(row, 2, QTableWidgetItem(dept['head_name']))
    
    def create_department(self):
        # Проверка прав на создание отдела
        if not self.task_manager.current_user or not self.task_manager.current_user.is_admin:
            QMessageBox.warning(self, 'Ошибка', 'Недостаточно прав для создания отдела')
            return
        
        # Здесь должно быть диалоговое окно создания отдела
        QMessageBox.information(self, 'Информация', 'Функционал создания отдела не реализован')
    
    def view_department(self):
        selected_row = self.departments_table.currentRow()
        if selected_row >= 0:
            dept_id = self.departments_table.item(selected_row, 0).text()
            dialog = DepartmentDetailsDialog(self.task_manager, dept_id)
            dialog.exec_()

class DepartmentDetailsDialog(QDialog):
    def init(self, task_manager, department_id):
        super().init()
        self.task_manager = task_manager
        self.department_id = department_id
        self.setWindowTitle("Информация об отделе")
        self.setMinimumSize(500, 400)
        self.initUI()
        self.load_department_info()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.name_label = QLabel()
        self.head_label = QLabel()

        self.layout.addWidget(QLabel("<b>Название отдела:</b>"))
        self.layout.addWidget(self.name_label)

        self.layout.addWidget(QLabel("<b>Руководитель:</b>"))
        self.layout.addWidget(self.head_label)

        self.layout.addWidget(QLabel("<b>Сотрудники:</b>"))
        self.employees_list = QTableWidget()
        self.employees_list.setColumnCount(2)
        self.employees_list.setHorizontalHeaderLabels(["ID", "Имя"])
        self.employees_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.layout.addWidget(self.employees_list)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        self.layout.addWidget(close_btn)

        self.setLayout(self.layout)

    def load_department_info(self):
        dept = self.task_manager.db.fetch_one(
            """
            SELECT d.name, u.full_name
            FROM departments d
            JOIN users u ON d.head_id = u.id
            WHERE d.id = %s
            """,
            (self.department_id,)
        )
        if dept:
            self.name_label.setText(dept[0])
            self.head_label.setText(dept[1])

        employees = self.task_manager.db.fetch_all(
            """
            SELECT u.id, u.full_name
            FROM department_employees de
            JOIN users u ON de.user_id = u.id
            WHERE de.department_id = %s
            """,
            (self.department_id,)
        )

        self.employees_list.setRowCount(0)
        for row, emp in enumerate(employees):
            self.employees_list.insertRow(row)
            self.employees_list.setItem(row, 0, QTableWidgetItem(emp["id"]))
            self.employees_list.setItem(row, 1, QTableWidgetItem(emp["full_name"]))

class MainWindow(QMainWindow):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.setWindowTitle('Система управления задачами')
        self.setMinimumSize(1000, 700)
        self.initUI()

    def initUI(self):
        self.tabs = QTabWidget()
        self.tasks_tab = TasksTab(self.task_manager)
        self.notifications_tab = NotificationsTab(self.task_manager)
        self.departments_tab = DepartmentsTab(self.task_manager)

        self.tabs.addTab(self.tasks_tab, 'Задачи')
        self.tabs.addTab(self.notifications_tab, 'Уведомления')
        self.tabs.addTab(self.departments_tab, 'Отделы')

        self.setCentralWidget(self.tabs)


class AppStack(QStackedWidget):
    def __init__(self, task_manager):
        super().__init__()
        self.task_manager = task_manager
        self.login_window = LoginWindow(task_manager)
        self.login_window.setParent(self)
        self.addWidget(self.login_window)
        self.main_window = None

    def open_main_window(self):
        self.main_window = MainWindow(self.task_manager)
        self.addWidget(self.main_window)
        self.setCurrentWidget(self.main_window)


def main():
    app = QApplication(sys.argv)

    # Настройки подключения к БД (замени при необходимости)
    db_params = {
        "dbname": "task_management",
        "user": "postgres",
        "password": "1234",
        "host": "localhost",
        "port": "5432"
    }

    smtp_params = {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "notifications@example.com",
        "smtp_password": "password123",
        "sender_email": "notifications@example.com"
    }

    task_manager = TaskManager(db_params, smtp_params)

    stack = AppStack(task_manager)
    stack.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()