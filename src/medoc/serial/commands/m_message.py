from medoc.serial.enums import DEVICE_TAG, COMMAND_ID

MAX_LENGTH = 512


class message:
    def __init__(self, command_tag: DEVICE_TAG):
        self.command_id = COMMAND_ID.Undefined
        self.command_array = None
        self.command_token = None
        self.command_tag = command_tag

    def __str__(self):
        return f"COMMAND: {self.command_id} TOKEN: {self.command_token} TAG: {self.command_tag}"
