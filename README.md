# Web Chat 

Консольный чат-клиент и сервер на Python с использованием **asyncio**. Приложение использует **TCP**-соединение для обмена сообщениями между клиентами и сервером.  

## Файлы проекта

- `server.py` — серверная часть
- `client.py` — клиентская часть

## Переменные окружения

### Для сервера
- `PORT` или `CHAT_PORT` — порт для запуска сервера (по умолчанию `8888`)

### Для клиента
- `CHAT_HOST` — адрес сервера (по умолчанию `127.0.0.1`)
- `PORT` или `CHAT_PORT` — порт сервера (по умолчанию `8888`)

## Запуск

### Сервер

**Linux / macOS (bash)**
```bash
export PORT=8888
python server.py
```
**Windows (PowerShell)**
```powershell
$env:PORT=8888
python server.py
```

### Клиент

**Linux / macOS (bash)**
```bash
export CHAT_HOST=127.0.0.1
export CHAT_PORT=8888
python client.py
```
**Windows (PowerShell)**
```powershell
$env:CHAT_HOST="127.0.0.1"
$env:CHAT_PORT=8888
python client.py
```
## Использование клиента
- При старте введите имя пользователя.  
- Печатайте сообщения и нажимайте Enter — они отправятся в чат.  
- Введите `quit` для выхода (клиент отправит событие `leave` и закроет соединение).

### Протокол
- Сообщения передаются в формате JSON, **одна строка на сообщение**, разделитель — `\n`.  
- Технические события:
  - Подключился:  
    ```json
    { "event": "join", "login": "name" }
    ```
  - Вышел:  
    ```json
    { "event": "leave", "login": "user_name" }
    ```
  - Сообщение:  
    ```json
    { "event": "message", "text": "...", "user": "user_name" }
    ```

### Дополнительно
- Все события логируются через `logging`. 
- Используется простая **ООП-структура**:
  - `ChatServer` и `ClientHandler` на сервере  
  - `ChatClient` на клиенте


