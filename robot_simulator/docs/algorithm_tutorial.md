# Як писати алгоритми керування

Цей туторіал — короткий шлях від «ніколи не писав control_step» до
працюючого алгоритму. Усі приклади запускаються в рамках цього
симулятора і опираються лише на вбудований `RobotAPI`.

## Загальна форма

```python
def control_step(robot):
    # 1. Прочитати стан робота через API.
    # 2. Обчислити команди.
    # 3. Викликати robot.set_velocity(...).
    pass
```

Файл алгоритму — це звичайний Python-файл з принаймні однією функцією
на ім'я `control_step(robot)`. Можна додавати власні допоміжні
функції, словники зі станом на рівні модуля, константи. Імпортувати
сторонні модулі заборонено — `math` і `random` уже доступні.

## Приклад 1: рух до цілі

Найпростіший випадок: коли курс невідповідний — повертайся,
інакше їдь вперед.

```python
def control_step(robot):
    if robot.distance_to_goal() < 0.2:
        robot.set_velocity(0.0, 0.0)
        return

    heading_error = robot.angle_to_goal() - robot.get_orientation()
    while heading_error > math.pi:
        heading_error -= 2 * math.pi
    while heading_error < -math.pi:
        heading_error += 2 * math.pi

    forward = 1.0 if abs(heading_error) < math.pi / 6 else 0.3
    robot.set_velocity(forward, 2.0 * heading_error)
```

Цей алгоритм на порожньому полі завжди дійде до цілі. У лабіринті —
впреться у стіну (фізика реальна, робот не проходить крізь
перешкоди), і вам це треба буде врахувати.

## Приклад 2: реактивне обходження перешкод

Підказка від сенсорів дозволяє відштовхуватись від найближчої
перешкоди. Ось ідея, реалізована у `examples/obstacle_avoidance.py`:

```python
def control_step(robot):
    safe = 0.8
    distances = robot.get_sensor_data()
    nearest = min(distances)

    if nearest < safe:
        # Найближча перешкода — у промені під номером nearest_idx.
        nearest_idx = distances.index(nearest)
        n = len(distances)
        local_angle = (2 * math.pi) * nearest_idx / n
        if local_angle > math.pi:
            local_angle -= 2 * math.pi
        # Поворот геть від перешкоди.
        sign = -1.0 if local_angle >= 0 else 1.0
        robot.set_velocity(0.25, sign * 1.5)
        return

    # Перешкод немає поруч — їдь до цілі.
    error = robot.angle_to_goal() - robot.get_orientation()
    robot.set_velocity(0.7, 2.0 * error)
```

## Приклад 3: PID на курсі

Тут показано, як зберегти стан між викликами `control_step`:

```python
KP, KI, KD = 2.5, 0.05, 0.6
_state = {"integral": 0.0, "previous_error": 0.0, "previous_time": 0.0}

def control_step(robot):
    if robot.distance_to_goal() < 0.2:
        robot.set_velocity(0.0, 0.0)
        return

    now = robot.get_time()
    dt = max(now - _state["previous_time"], 0.02)

    error = robot.angle_to_goal() - robot.get_orientation()
    while error > math.pi: error -= 2 * math.pi
    while error < -math.pi: error += 2 * math.pi

    _state["integral"] += error * dt
    derivative = (error - _state["previous_error"]) / dt
    omega = KP * error + KI * _state["integral"] + KD * derivative
    omega = max(-2.0, min(2.0, omega))

    forward = 1.0 if abs(error) < math.pi / 6 else 0.5
    robot.set_velocity(forward, omega)

    _state["previous_error"] = error
    _state["previous_time"] = now
```

## Дебаг через `robot.log`

Легко друкувати поточний стан у консоль:

```python
robot.log(f"d={robot.distance_to_goal():.2f}  v={robot.get_velocity()}")
```

Не зловживайте — друк раз на тик з частотою 50 Гц забиває консоль.
Зручний шаблон — друкувати лише при переходах режиму (як у
`combined_navigation.py`).

## Обмеження, які варто пам'ятати

* `set_velocity` обрізається до фізичних меж робота (за замовчуванням
  ±1.0 м/с лінійна, ±2.0 рад/с кутова).
* Робот фізично упирається у стіни. Якщо ваш алгоритм втикає робот у
  кут і не виходить з нього — швидкість буде стабільно 0.
* Виняток у вашому коді — не аварія: traceback з'явиться у консолі,
  симуляція зупиниться, ви виправите і знову натиснете **Run**.
* Кожен **Run** з нуля компілює код і скидає всі словники зі станом.
  Симуляція автоматично робить `Reset`, якщо попередній запуск
  завершився успіхом або колізією.

## Куди далі

Подивіться на `examples/wall_following.py` для алгоритму, який не
використовує позицію цілі — лише сенсори. У `combined_navigation.py`
показано перемикання режимів через словник стану. Беріть будь-який
файл як стартову точку для свого варіанту.
