# app/events/event_bus.py
class EventBus:
    _listeners = {}

    @classmethod
    def subscribe(cls, event_name: str, callback):
        if event_name not in cls._listeners:
            cls._listeners[event_name] = []
        cls._listeners[event_name].append(callback)

    @classmethod
    def emit(cls, event_name: str, payload: dict):
        if event_name in cls._listeners:
            for callback in cls._listeners[event_name]:
                callback(payload)