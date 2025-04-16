import datetime
import hashlib
import uuid
import psycopg2
import psycopg2.extras
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional, Union, Tuple, Any


class Database:
    def __init__(self, dbname: str, user: str, password: str, host: str = "localhost", port: str = "5432"):
        self.conn_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }
        self.connection = None
    
    def connect(self) -> None:
        try:
            self.connection = psycopg2.connect(**self.conn_params)
        except psycopg2.Error as e:
            print(f"Ошибка подключения к базе данных: {e}")
            raise
    
    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()
    
    def execute(self, query: str, params: Optional[Tuple] = None) -> None:
        """Выполнение запроса без возврата данных (INSERT, UPDATE, DELETE)"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
        except psycopg2.Error as e:
            self.connection.rollback()
            print(f"Ошибка выполнения запроса: {e}")
            raise
    
    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Tuple]:
        """Выполнение запроса с возвратом одной строки"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Ошибка выполнения запроса: {e}")
            raise
    
    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """Выполнение запроса с возвратом всех строк"""
        if not self.connection:
            self.connect()
        
        try:
            with self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Ошибка выполнения запроса: {e}")
            raise
    
    def initialize_db(self) -> None:
        """Создание необходимых таблиц в базе данных"""
        # Создание таблицы пользователей
        self.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(36) PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(64) NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                email VARCHAR(100),
                notification_preferences JSONB DEFAULT '{"email": true, "in_app": true}'
            )
        """)
        
        # Создание таблицы отделов
        self.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                head_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE RESTRICT
            )
        """)
        
        # Создание таблицы сотрудников отдела
        self.execute("""
            CREATE TABLE IF NOT EXISTS department_employees (
                department_id VARCHAR(36) REFERENCES departments(id) ON DELETE CASCADE,
                user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
                PRIMARY KEY (department_id, user_id)
            )
        """)
        
        # Создание таблицы задач
        self.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id VARCHAR(36) PRIMARY KEY,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                created_by VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                assigned_to VARCHAR(36) REFERENCES users(id) ON DELETE SET NULL,
                department_id VARCHAR(36) REFERENCES departments(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deadline TIMESTAMP,
                status VARCHAR(20) NOT NULL DEFAULT 'новая',
                priority VARCHAR(20) DEFAULT 'обычный'
            )
        """)
        
        # Создание таблицы комментариев
        self.execute("""
            CREATE TABLE IF NOT EXISTS task_comments (
                id VARCHAR(36) PRIMARY KEY,
                task_id VARCHAR(36) NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                text TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Создание таблицы уведомлений
        self.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL,
                type VARCHAR(50) NOT NULL,
                related_id VARCHAR(36),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)


class NotificationService:
    def __init__(self, db: Database, smtp_server: str = None, smtp_port: int = 587, 
                 smtp_username: str = None, smtp_password: str = None, sender_email: str = None):
        self.db = db
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.sender_email = sender_email
    
    def create_notification(self, user_id: str, message: str, 
                           notification_type: str, related_id: Optional[str] = None) -> str:
        """Создание уведомления в системе"""
        notification_id = str(uuid.uuid4())
        
        self.db.execute(
            """
            INSERT INTO notifications (id, user_id, message, type, related_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (notification_id, user_id, message, notification_type, related_id, datetime.datetime.now())
        )
        
        return notification_id
    
    def send_email_notification(self, user_id: str, subject: str, message: str) -> bool:
        """Отправка уведомления по электронной почте"""
        if not self.smtp_server or not self.sender_email:
            return False
        
        # Получение email пользователя
        user_info = self.db.fetch_one(
            "SELECT email, notification_preferences FROM users WHERE id = %s",
            (user_id,)
        )
        
        if not user_info or not user_info[0] or not user_info[1].get('email', False):
            return False
        
        user_email = user_info[0]
        
        try:
            # Настройка сообщения
            msg = MIMEMultipart()
            msg['From'] = self.sender_email
            msg['To'] = user_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'html'))
            
            # Отправка письма
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Ошибка отправки email: {e}")
            return False
    
    def notify_task_assignment(self, task_id: str, user_id: str) -> None:
        """Уведомление о назначении задачи"""
        # Получение информации о задаче
        task_info = self.db.fetch_one(
            """
            SELECT t.title, u.full_name 
            FROM tasks t 
            JOIN users u ON t.created_by = u.id 
            WHERE t.id = %s
            """,
            (task_id,)
        )
        
        if not task_info:
            return
        
        task_title, creator_name = task_info
        
        message = f"Вам назначена новая задача: {task_title} от пользователя {creator_name}"
        
        # Создание уведомления в системе
        self.create_notification(user_id, message, "task_assignment", task_id)
        
        # Отправка email
        email_subject = "Новая задача назначена"
        email_message = f"""
        <html>
        <body>
            <h2>Вам назначена новая задача</h2>
            <p><strong>Название:</strong> {task_title}</p>
            <p><strong>От:</strong> {creator_name}</p>
            <p>Пожалуйста, войдите в систему для просмотра деталей задачи.</p>
        </body>
        </html>
        """
        
        self.send_email_notification(user_id, email_subject, email_message)
    
    def notify_task_status_change(self, task_id: str, new_status: str) -> None:
        """Уведомление об изменении статуса задачи"""
        # Получение информации о задаче и связанных пользователях
        task_info = self.db.fetch_one(
            """
            SELECT t.title, t.created_by, t.assigned_to
            FROM tasks t
            WHERE t.id = %s
            """,
            (task_id,)
        )
        
        if not task_info:
            return
        
        task_title, creator_id, assigned_to = task_info
        
        # Определение кого уведомлять
        notify_users = set()
        if creator_id:
            notify_users.add(creator_id)
        if assigned_to and assigned_to != creator_id:
            notify_users.add(assigned_to)
        
        status_label = {
            "новая": "создана",
            "в работе": "взята в работу",
            "выполнена": "выполнена",
            "отменена": "отменена"
        }.get(new_status, new_status)
        
        for user_id in notify_users:
            message = f"Задача '{task_title}' {status_label}"
            
            # Создание уведомления в системе
            self.create_notification(user_id, message, "task_status_change", task_id)
            
            # Отправка email
            email_subject = f"Изменение статуса задачи: {task_title}"
            email_message = f"""
            <html>
            <body>
                <h2>Изменение статуса задачи</h2>
                <p><strong>Задача:</strong> {task_title}</p>
                <p><strong>Новый статус:</strong> {new_status}</p>
                <p>Пожалуйста, войдите в систему для просмотра деталей задачи.</p>
            </body>
            </html>
            """
            
            self.send_email_notification(user_id, email_subject, email_message)
    
    def notify_new_comment(self, comment_id: str) -> None:
        """Уведомление о новом комментарии к задаче"""
        # Получение информации о комментарии и задаче
        comment_info = self.db.fetch_one(
            """
            SELECT c.text, c.user_id, t.id, t.title, t.created_by, t.assigned_to, u.full_name
            FROM task_comments c
            JOIN tasks t ON c.task_id = t.id
            JOIN users u ON c.user_id = u.id
            WHERE c.id = %s
            """,
            (comment_id,)
        )
        
        if not comment_info:
            return
        
        comment_text, commenter_id, task_id, task_title, creator_id, assigned_to, commenter_name = comment_info
        
        # Определение кого уведомлять (кроме автора комментария)
        notify_users = set()
        if creator_id and creator_id != commenter_id:
            notify_users.add(creator_id)
        if assigned_to and assigned_to != commenter_id and assigned_to != creator_id:
            notify_users.add(assigned_to)
        
        for user_id in notify_users:
            message = f"Новый комментарий от {commenter_name} к задаче '{task_title}'"
            
            # Создание уведомления в системе
            self.create_notification(user_id, message, "new_comment", task_id)
            
            # Отправка email
            email_subject = f"Новый комментарий к задаче: {task_title}"
            email_message = f"""
            <html>
            <body>
                <h2>Новый комментарий к задаче</h2>
                <p><strong>Задача:</strong> {task_title}</p>
                <p><strong>От:</strong> {commenter_name}</p>
                <p><strong>Комментарий:</strong> {comment_text}</p>
                <p>Пожалуйста, войдите в систему для просмотра деталей задачи.</p>
            </body>
            </html>
            """
            
            self.send_email_notification(user_id, email_subject, email_message)
    
    def get_user_notifications(self, user_id: str, limit: int = 20, 
                              only_unread: bool = False) -> List[Dict[str, Any]]:
        """Получение уведомлений пользователя"""
        query = """
            SELECT id, message, type, related_id, created_at, is_read
            FROM notifications
            WHERE user_id = %s
        """
        
        if only_unread:
            query += " AND is_read = FALSE"
        
        query += " ORDER BY created_at DESC LIMIT %s"
        
        notifications = self.db.fetch_all(query, (user_id, limit))
        
        return [dict(n) for n in notifications]
    
    def mark_notification_as_read(self, notification_id: str) -> bool:
        """Отметить уведомление как прочитанное"""
        try:
            self.db.execute(
                "UPDATE notifications SET is_read = TRUE WHERE id = %s",
                (notification_id,)
            )
            return True
        except:
            return False
    
    def mark_all_notifications_as_read(self, user_id: str) -> bool:
        """Отметить все уведомления пользователя как прочитанные"""
        try:
            self.db.execute(
                "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE",
                (user_id,)
            )
            return True
        except:
            return False


class User:
    def __init__(self, id: str, username: str, password_hash: str, full_name: str, 
                is_admin: bool = False, email: Optional[str] = None, 
                notification_preferences: Optional[Dict] = None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.full_name = full_name
        self.is_admin = is_admin
        self.email = email
        self.notification_preferences = notification_preferences or {"email": True, "in_app": True}
    
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    def verify_password(self, password: str) -> bool:
        return self.hash_password(password) == self.password_hash
    
    def __str__(self) -> str:
        return f"{self.full_name} ({self.username})"


class TaskManager:
    def __init__(self, db_params: Dict[str, str], smtp_params: Optional[Dict[str, Any]] = None):
        self.db = Database(**db_params)
        self.db.connect()
        self.db.initialize_db()
        
        # Инициализация сервиса уведомлений
        self.notification_service = NotificationService(self.db, **(smtp_params or {}))
        
        self.current_user = None
    
    def __del__(self):
        self.db.disconnect()
    
    def register_user(self, username: str, password: str, full_name: str, 
                     is_admin: bool = False, email: Optional[str] = None) -> Union[str, bool]:
        """Регистрация нового пользователя"""
        # Проверка наличия пользователя с таким именем
        existing_user = self.db.fetch_one(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )
        
        if existing_user:
            return "Пользователь с таким именем уже существует"
        
        user_id = str(uuid.uuid4())
        password_hash = User.hash_password(password)
        
        try:
            self.db.execute(
                """
                INSERT INTO users (id, username, password_hash, full_name, is_admin, email)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, username, password_hash, full_name, is_admin, email)
            )
            return user_id
        except Exception as e:
            return f"Ошибка регистрации пользователя: {str(e)}"
    
    def login(self, username: str, password: str) -> bool:
        """Вход пользователя в систему"""
        user_data = self.db.fetch_one(
            """
            SELECT id, username, password_hash, full_name, is_admin, email, notification_preferences
            FROM users WHERE username = %s
            """,
            (username,)
        )
        
        if not user_data:
            return False
        
        user = User(
            id=user_data[0], 
            username=user_data[1], 
            password_hash=user_data[2], 
            full_name=user_data[3], 
            is_admin=user_data[4],
            email=user_data[5],
            notification_preferences=user_data[6]
        )
        
        if user.verify_password(password):
            self.current_user = user
            return True
        
        return False
    
    def logout(self) -> None:
        """Выход из системы"""
        self.current_user = None
    
    def create_department(self, name: str, head_id: str) -> Union[str, bool]:
        """Создание нового отдела"""
        if not self.current_user or not self.current_user.is_admin:
            return "Недостаточно прав для создания отдела"
        
        # Проверка существования пользователя и является ли он администратором
        head_user = self.db.fetch_one(
            "SELECT is_admin FROM users WHERE id = %s",
            (head_id,)
        )
        
        if not head_user:
            return "Пользователь не найден"
        
        if not head_user[0]:
            return "Руководитель отдела должен быть администратором"
        
        department_id = str(uuid.uuid4())
        
        try:
            self.db.execute(
                """
                INSERT INTO departments (id, name, head_id)
                VALUES (%s, %s, %s)
                """,
                (department_id, name, head_id)
            )
            return department_id
        except Exception as e:
            return f"Ошибка создания отдела: {str(e)}"
    
    def add_employee_to_department(self, user_id: str, department_id: str) -> Union[str, bool]:
        """Добавление сотрудника в отдел"""
        if not self.current_user or not self.current_user.is_admin:
            return "Недостаточно прав для добавления сотрудников"
        
        # Проверка существования пользователя и отдела
        user = self.db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,))
        department = self.db.fetch_one("SELECT id FROM departments WHERE id = %s", (department_id,))
        
        if not user:
            return "Пользователь не найден"
        
        if not department:
            return "Отдел не найден"
        
        try:
            # Проверка, не состоит ли пользователь уже в этом отделе
            existing = self.db.fetch_one(
                """
                SELECT 1 FROM department_employees 
                WHERE department_id = %s AND user_id = %s
                """,
                (department_id, user_id)
            )
            
            if existing:
                return "Пользователь уже является сотрудником этого отдела"
            
            # Добавление пользователя в отдел
            self.db.execute(
                """
                INSERT INTO department_employees (department_id, user_id)
                VALUES (%s, %s)
                """,
                (department_id, user_id)
            )
            return True
        except Exception as e:
            return f"Ошибка добавления сотрудника: {str(e)}"
    
    def create_task(self, title: str, description: str, department_id: Optional[str] = None,
                   assigned_to: Optional[str] = None, deadline: Optional[datetime.datetime] = None,
                   priority: str = "обычный") -> Union[str, bool]:
        """Создание новой задачи"""
        if not self.current_user:
            return "Вы должны войти в систему для создания задачи"
        
        # Проверки перед созданием задачи
        if department_id:
            # Проверка существования отдела
            department = self.db.fetch_one(
                """
                SELECT d.id, d.head_id FROM departments d
                WHERE d.id = %s
                """,
                (department_id,)
            )
            
            if not department:
                return "Указанный отдел не найден"
            
            # Проверка прав: администратор или руководитель отдела
            if not self.current_user.is_admin and department[1] != self.current_user.id:
                return "Недостаточно прав для создания задачи в этом отделе"
        
        # Проверка назначаемого пользователя
        if assigned_to:
            # Проверка существования пользователя
            assigned_user = self.db.fetch_one(
                "SELECT id FROM users WHERE id = %s",
                (assigned_to,)
            )
            
            if not assigned_user:
                return "Указанный пользователь не найден"
            
            # Если задача в отделе, проверяем что пользователь из этого отдела
            if department_id:
                employee = self.db.fetch_one(
                    """
                    SELECT 1 FROM department_employees
                    WHERE department_id = %s AND user_id = %s
                    """,
                    (department_id, assigned_to)
                )
                
                if not employee:
                    return "Указанный пользователь не является сотрудником данного отдела"
        
        # Создание задачи
        task_id = str(uuid.uuid4())
        
        try:
            self.db.execute(
                """
                INSERT INTO tasks (id, title, description, created_by, assigned_to, department_id, 
                                 created_at, deadline, status, priority)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (task_id, title, description, self.current_user.id, assigned_to, department_id,
                 datetime.datetime.now(), deadline, "новая", priority)
            )
            
            # Если задача назначена на пользователя, отправляем уведомление
            if assigned_to:
                self.notification_service.notify_task_assignment(task_id, assigned_to)
            
            return task_id
        except Exception as e:
            return f"Ошибка создания задачи: {str(e)}"
    
    def assign_task(self, task_id: str, user_id: str) -> Union[str, bool]:
        """Назначение задачи исполнителю"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Получение информации о задаче
        task = self.db.fetch_one(
            """
            SELECT t.created_by, t.department_id, t.title, t.status
            FROM tasks t
            WHERE t.id = %s
            """,
            (task_id,)
        )
        
        if not task:
            return "Задача не найдена"
        
        created_by, department_id, task_title, status = task
        
        # Проверка прав на назначение задачи
        has_permission = False
        
        # Администраторы имеют полные права
        if self.current_user.is_admin:
            has_permission = True
        # Создатели задач могут их назначать
        elif self.current_user.id == created_by:
            has_permission = True
        # Руководители отделов могут назначать задачи в своих отделах
        elif department_id:
            department_head = self.db.fetch_one(
                "SELECT head_id FROM departments WHERE id = %s",
                (department_id,)
            )
            if department_head and department_head[0] == self.current_user.id:
                has_permission = True
        
        if not has_permission:
            return "Недостаточно прав для назначения этой задачи"
        
        # Проверка существования пользователя
        user = self.db.fetch_one("SELECT id FROM users WHERE id = %s", (user_id,))
        if not user:
            return "Пользователь не найден"
        
        # Если задача привязана к отделу, проверяем что пользователь из этого отдела
        if department_id:
            employee = self.db.fetch_one(
                """
                SELECT 1 FROM department_employees
                WHERE department_id = %s AND user_id = %s
                """,
                (department_id, user_id)
            )
            
            if not employee:
                return "Назначенный пользователь не является сотрудником данного отдела"
        
        try:
            # Назначение задачи и обновление статуса
            self.db.execute(
                """
                UPDATE tasks
                SET assigned_to = %s, status = 'в работе'
                WHERE id = %s
                """,
                (user_id, task_id)
            )
            
            # Отправка уведомления
            self.notification_service.notify_task_assignment(task_id, user_id)
            
            return True
        except Exception as e:
            return f"Ошибка при назначении задачи: {str(e)}"
    
    def update_task_status(self, task_id: str, status: str) -> Union[str, bool]:
        """Обновление статуса задачи"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Валидация статуса
        valid_statuses = ["новая", "в работе", "выполнена", "отменена"]
        if status not in valid_statuses:
            return f"Некорректный статус. Допустимые значения: {', '.join(valid_statuses)}"
        
        # Получение информации о задаче
        task = self.db.fetch_one(
            """
            SELECT t.created_by, t.assigned_to, t.department_id
            FROM tasks t
            WHERE t.id = %s
            """,
            (task_id,)
        )
        
        if not task:
            return "Задача не найдена"
        
        created_by, assigned_to, department_id = task
        
        # Проверка прав на изменение статуса
        has_permission = False
        
        # Администраторы имеют полные права
        if self.current_user.is_admin:
            has_permission = True
        # Создатели задач могут менять их статус
        elif self.current_user.id == created_by:
            has_permission = True
        # Назначенные исполнители могут менять статус
        elif self.current_user.id == assigned_to:
            has_permission = True
        # Руководители отделов могут менять статус задач своего отдела
        elif department_id:
            department_head = self.db.fetch_one(
                "SELECT head_id FROM departments WHERE id = %s",
                (department_id,)
            )
            if department_head and department_head[0] == self.current_user.id:
                has_permission = True
        
        if not has_permission:
            return "Недостаточно прав для изменения статуса этой задачи"
        
        try:
            # Обновление статуса задачи
            self.db.execute(
                "UPDATE tasks SET status = %s WHERE id = %s",
                (status, task_id)
            )
            
            # Отправка уведомления об изменении статуса
            self.notification_service.notify_task_status_change(task_id, status)
            
            return True
        except Exception as e:
            return f"Ошибка при обновлении статуса задачи: {str(e)}"
    
    def add_task_comment(self, task_id: str, comment_text: str) -> Union[str, bool]:
        """Добавление комментария к задаче"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Проверка существования задачи
        task = self.db.fetch_one(
            "SELECT id FROM tasks WHERE id = %s",
            (task_id,)
        )
        
        if not task:
            return "Задача не найдена"
        
        comment_id = str(uuid.uuid4())
        
        try:
            self.db.execute(
                """
                INSERT INTO task_comments (id, task_id, user_id, text, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (comment_id, task_id, self.current_user.id, comment_text, datetime.datetime.now())
            )
            
            # Отправка уведомления о новом комментарии
            self.notification_service.notify_new_comment(comment_id)
            
            return comment_id
        except Exception as e:
            return f"Ошибка при добавлении комментария: {str(e)}"
    
    def get_user_tasks(self, user_id: Optional[str] = None, 
                      status: Optional[str] = None, 
                      page: int = 1, 
                      per_page: int = 20) -> Union[List[Dict[str, Any]], str]:
        """Получение задач пользователя (созданных или назначенных)"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Если пользователь не указан, используем текущего пользователя
        if not user_id:
            user_id = self.current_user.id
        elif user_id != self.current_user.id and not self.current_user.is_admin:
            # Проверка прав: только администратор может смотреть задачи других пользователей
            return "Недостаточно прав для просмотра задач другого пользователя"
        
        # Базовый запрос
        query = """
            SELECT t.id, t.title, t.description, t.status, t.created_at, t.deadline, t.priority,
                   d.name as department_name, 
                   creator.full_name as creator_name,
                   assignee.full_name as assignee_name
            FROM tasks t
            LEFT JOIN departments d ON t.department_id = d.id
            LEFT JOIN users creator ON t.created_by = creator.id
            LEFT JOIN users assignee ON t.assigned_to = assignee.id
            WHERE (t.created_by = %s OR t.assigned_to = %s)
        """
        
        params = [user_id, user_id]
        
        # Добавление фильтра по статусу
        if status:
            query += " AND t.status = %s"
            params.append(status)
        
        # Добавление пагинации
        offset = (page - 1) * per_page
        query += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        try:
            tasks = self.db.fetch_all(query, tuple(params))
            return [dict(task) for task in tasks]
        except Exception as e:
            return f"Ошибка при получении задач: {str(e)}"
    
    def get_department_tasks(self, department_id: str, 
                            status: Optional[str] = None,
                            page: int = 1, 
                            per_page: int = 20) -> Union[List[Dict[str, Any]], str]:
        """Получение задач отдела"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Проверка существования отдела
        department = self.db.fetch_one(
            "SELECT id, head_id FROM departments WHERE id = %s",
            (department_id,)
        )
        
        if not department:
            return "Отдел не найден"
        
        # Проверка прав: администратор, руководитель отдела или сотрудник отдела
        has_permission = False
        
        # Администраторы имеют полные права
        if self.current_user.is_admin:
            has_permission = True
        # Руководитель отдела имеет доступ к задачам своего отдела
        elif department[1] == self.current_user.id:
            has_permission = True
        # Сотрудники отдела имеют доступ к задачам своего отдела
        else:
            employee = self.db.fetch_one(
                """
                SELECT 1 FROM department_employees
                WHERE department_id = %s AND user_id = %s
                """,
                (department_id, self.current_user.id)
            )
            if employee:
                has_permission = True
        
        if not has_permission:
            return "Недостаточно прав для просмотра задач отдела"
        
        # Базовый запрос
        query = """
            SELECT t.id, t.title, t.description, t.status, t.created_at, t.deadline, t.priority,
                   creator.full_name as creator_name,
                   assignee.full_name as assignee_name
            FROM tasks t
            LEFT JOIN users creator ON t.created_by = creator.id
            LEFT JOIN users assignee ON t.assigned_to = assignee.id
            WHERE t.department_id = %s
        """
        
        params = [department_id]
        
        # Добавление фильтра по статусу
        if status:
            query += " AND t.status = %s"
            params.append(status)
        
        # Добавление пагинации
        offset = (page - 1) * per_page
        query += " ORDER BY t.created_at DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        try:
            tasks = self.db.fetch_all(query, tuple(params))
            return [dict(task) for task in tasks]
        except Exception as e:
            return f"Ошибка при получении задач отдела: {str(e)}"
    
    def get_task_comments(self, task_id: str) -> Union[List[Dict[str, Any]], str]:
        """Получение комментариев к задаче"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Получение информации о задаче для проверки прав доступа
        task = self.db.fetch_one(
            """
            SELECT t.created_by, t.assigned_to, t.department_id
            FROM tasks t
            WHERE t.id = %s
            """,
            (task_id,)
        )
        
        if not task:
            return "Задача не найдена"
        
        created_by, assigned_to, department_id = task
        
        # Проверка прав доступа к комментариям задачи
        has_permission = False
        
        # Администраторы имеют полные права
        if self.current_user.is_admin:
            has_permission = True
        # Создатели и исполнители задач имеют доступ к комментариям
        elif self.current_user.id in (created_by, assigned_to):
            has_permission = True
        # Руководители отделов имеют доступ к комментариям задач своего отдела
        elif department_id:
            department_head = self.db.fetch_one(
                "SELECT head_id FROM departments WHERE id = %s",
                (department_id,)
            )
            if department_head and department_head[0] == self.current_user.id:
                has_permission = True
            # Сотрудники отдела имеют доступ к комментариям задач своего отдела
            else:
                employee = self.db.fetch_one(
                    """
                    SELECT 1 FROM department_employees
                    WHERE department_id = %s AND user_id = %s
                    """,
                    (department_id, self.current_user.id)
                )
                if employee:
                    has_permission = True
        
        if not has_permission:
            return "Недостаточно прав для просмотра комментариев к этой задаче"
        
        try:
            comments = self.db.fetch_all(
                """
                SELECT c.id, c.text, c.created_at, u.full_name as user_name
                FROM task_comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.task_id = %s
                ORDER BY c.created_at ASC
                """,
                (task_id,)
            )
            
            return [dict(comment) for comment in comments]
        except Exception as e:
            return f"Ошибка при получении комментариев: {str(e)}"
    
    def get_unread_notifications_count(self) -> Union[int, str]:
        """Получение количества непрочитанных уведомлений"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        try:
            count = self.db.fetch_one(
                """
                SELECT COUNT(*) FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                """,
                (self.current_user.id,)
            )
            
            return count[0] if count else 0
        except Exception as e:
            return f"Ошибка при получении количества уведомлений: {str(e)}"
    
    def get_user_statistics(self, user_id: Optional[str] = None) -> Union[Dict[str, Any], str]:
        """Получение статистики по задачам пользователя"""
        if not self.current_user:
            return "Вы должны войти в систему"
        
        # Если пользователь не указан, используем текущего пользователя
        if not user_id:
            user_id = self.current_user.id
        elif user_id != self.current_user.id and not self.current_user.is_admin:
            # Проверка прав: только администратор может смотреть статистику других пользователей
            return "Недостаточно прав для просмотра статистики другого пользователя"
        
        try:
            # Статистика по задачам, где пользователь исполнитель
            assigned_stats = self.db.fetch_one(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'новая') as new_count,
                    COUNT(*) FILTER (WHERE status = 'в работе') as in_progress_count,
                    COUNT(*) FILTER (WHERE status = 'выполнена') as completed_count,
                    COUNT(*) FILTER (WHERE status = 'отменена') as cancelled_count
                FROM tasks
                WHERE assigned_to = %s
                """,
                (user_id,)
            )
            
            # Статистика по задачам, где пользователь создатель
            created_stats = self.db.fetch_one(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'новая') as new_count,
                    COUNT(*) FILTER (WHERE status = 'в работе') as in_progress_count,
                    COUNT(*) FILTER (WHERE status = 'выполнена') as completed_count,
                    COUNT(*) FILTER (WHERE status = 'отменена') as cancelled_count
                FROM tasks
                WHERE created_by = %s
                """,
                (user_id,)
            )
            
            # Статистика по дедлайнам
            deadline_stats = self.db.fetch_one(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE deadline < CURRENT_TIMESTAMP AND status NOT IN ('выполнена', 'отменена')) as overdue_count,
                    COUNT(*) FILTER (WHERE deadline BETWEEN CURRENT_TIMESTAMP AND CURRENT_TIMESTAMP + INTERVAL '1 day' AND status NOT IN ('выполнена', 'отменена')) as due_today_count
                FROM tasks
                WHERE assigned_to = %s AND deadline IS NOT NULL
                """,
                (user_id,)
            )
            
            return {
                "assigned_tasks": {
                    "new": assigned_stats[0] if assigned_stats else 0,
                    "in_progress": assigned_stats[1] if assigned_stats else 0,
                    "completed": assigned_stats[2] if assigned_stats else 0,
                    "cancelled": assigned_stats[3] if assigned_stats else 0,
                    "total": sum(assigned_stats) if assigned_stats else 0
                },
                "created_tasks": {
                    "new": created_stats[0] if created_stats else 0,
                    "in_progress": created_stats[1] if created_stats else 0,
                    "completed": created_stats[2] if created_stats else 0,
                    "cancelled": created_stats[3] if created_stats else 0,
                    "total": sum(created_stats) if created_stats else 0
                },
                "deadlines": {
                    "overdue": deadline_stats[0] if deadline_stats else 0,
                    "due_today": deadline_stats[1] if deadline_stats else 0
                }
            }
            
        except Exception as e:
            return f"Ошибка при получении статистики: {str(e)}"


# Пример использования системы
if __name__ == "__main__":
    # Параметры подключения к базе данных
    db_params = {
        "dbname": "task_management",
        "user": "postgres",
        "password": "1234",
        "host": "localhost",
        "port": "5432"
    }
    
    # Параметры для отправки email-уведомлений
    smtp_params = {
        "smtp_server": "smtp.example.com",
        "smtp_port": 587,
        "smtp_username": "notifications@example.com",
        "smtp_password": "password123",
        "sender_email": "notifications@example.com"
    }
    
    # Инициализация менеджера задач
    manager = TaskManager(db_params, smtp_params)
    
    # Регистрация администраторов
    admin1_id = manager.register_user(
        username="admin1", 
        password="password123", 
        full_name="Иванов Иван", 
        is_admin=True,
        email="admin1@example.com"
    )
    
    admin2_id = manager.register_user(
        username="admin2", 
        password="password123", 
        full_name="Петров Петр", 
        is_admin=True,
        email="admin2@example.com"
    )
    
    # Вход в систему
    if manager.login("admin1", "password123"):
        print("Вход в систему выполнен успешно")
        
        # Создание отдела и назначение руководителя
        if isinstance(admin1_id, str):
            it_department_id = manager.create_department("IT отдел", admin1_id)
            
            if isinstance(it_department_id, str):
                print(f"Создан отдел с ID: {it_department_id}")
                
                # Регистрация сотрудников
                employee1_id = manager.register_user(
                    username="user1", 
                    password="pass123", 
                    full_name="Сидоров Алексей",
                    email="user1@example.com"
                )
                
                employee2_id = manager.register_user(
                    username="user2", 
                    password="pass123", 
                    full_name="Смирнова Мария",
                    email="user2@example.com"
                )
                
                if isinstance(employee1_id, str) and isinstance(employee2_id, str):
                    # Добавление сотрудников в отдел
                    manager.add_employee_to_department(employee1_id, it_department_id)
                    manager.add_employee_to_department(employee2_id, it_department_id)
                    
                    # Создание задачи
                    task_id = manager.create_task(
                        title="Настройка сервера",
                        description="Необходимо настроить новый сервер для отдела бухгалтерии",
                        department_id=it_department_id,
                        deadline=datetime.datetime.now() + datetime.timedelta(days=5),
                        priority="высокий"
                    )
                    
                    if isinstance(task_id, str):
                        print(f"Создана задача с ID: {task_id}")
                        
                        # Назначение задачи сотруднику
                        result = manager.assign_task(task_id, employee1_id)
                        if result is True:
                            print("Задача успешно назначена")
                        
                        # Добавление комментария
                        comment_id = manager.add_task_comment(
                            task_id,
                            "Не забудьте настроить резервное копирование"
                        )
                        
                        if isinstance(comment_id, str):
                            print(f"Добавлен комментарий с ID: {comment_id}")
                        
                        # Вход другим пользователем
                        manager.logout()
                        if manager.login("user1", "pass123"):
                            print("Вход под пользователем user1 выполнен успешно")
                            
                            # Получение списка уведомлений
                            notifications = manager.notification_service.get_user_notifications(employee1_id)
                            print(f"Непрочитанных уведомлений: {len(notifications)}")
                            
                            for notification in notifications:
                                print(f"- {notification['message']}")
                                # Отметка уведомления как прочитанного
                                manager.notification_service.mark_notification_as_read(notification['id'])
                            
                            # Обновление статуса задачи
                            manager.update_task_status(task_id, "выполнена")
                            
                            # Добавление комментария о выполнении
                            manager.add_task_comment(
                                task_id,
                                "Задача выполнена, сервер настроен и протестирован"
                            )
                            
                            # Получение статистики по своим задачам
                            stats = manager.get_user_statistics()
                            if isinstance(stats, dict):
                                print("\nСтатистика пользователя:")
                                print(f"Выполненных задач: {stats['assigned_tasks']['completed']}")
                                print(f"Всего назначенных задач: {stats['assigned_tasks']['total']}")