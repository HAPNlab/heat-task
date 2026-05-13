from medoc.serial.commands.r_finite_ramp_by_time import finite_ramp_by_time_response
from medoc.serial.commands.r_get_status_TCU import get_statusTCU_response
from medoc.serial.commands.r_get_version_command import get_version_response
from medoc.serial.commands.response import response


def build_response(command_id):
    if command_id == 19:
        return response()
    if command_id == 33:
        return get_statusTCU_response()
    if command_id in (22, 27, 41, 47, 25, 45):
        return response()
    if command_id == 37:
        return get_version_response()
    if command_id == 28:
        return finite_ramp_by_time_response()
    return None
