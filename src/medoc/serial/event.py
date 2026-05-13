import weakref


class Event:
    def __init__(self):
        self.receivers: list = []
        self.ignore_error = True

    def connect(self, callback):
        if not callable(callback):
            raise TypeError("Tried to connect non-callable to event!")
        self.receivers.append(weakref.WeakMethod(callback))

    def erase(self, callback):
        self.receivers.remove(callback)

    def clear(self):
        self.receivers.clear()

    def emit(self, *args):
        for i in range(len(self.receivers)):
            callback = self.receivers[i]()
            if callback is None:
                del self.receivers[i]
                i -= 1
                continue
            if self.ignore_error:
                try:
                    callback(*args)
                except TypeError:
                    pass
            else:
                callback(*args)


class TypedEvent(Event):
    def __init__(self, *param_types):
        super().__init__()
        self.param_types = param_types

    def emit(self, *args):
        emit_types = tuple(type(param) for param in args)
        if emit_types != self.param_types:
            raise TypeError(
                f"TypedEvent emit expected argument types '{self.param_types}', "
                f"but got `{emit_types}` instead."
            )
        return super().emit(*args)

    def connect(self, callback):
        callback_args = callback.__code__.co_varnames
        l = len(callback_args)
        if l > 0 and callback_args[0] == 'self':
            l -= 1
        if l != len(self.param_types):
            raise TypeError(
                f"TypedEvent connect expected argument count of {len(self.param_types)}, "
                f"but target has {l}."
            )
        return super().connect(callback)
