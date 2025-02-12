from typing import Dict

from utils.constants import LIMIT_FILE_SIZE, LIMIT_DIRECTORY_SIZE


def check_size_limits(obj_dict: Dict, file_size: float) -> bool:
    """
    Проверка на лимит по размеру файла, размеру существующих файлов в папке, кол-ву файлов
    :return:
    """
    if file_size > LIMIT_FILE_SIZE or file_size <= 0:
        return False
    dir_size = sum(list(obj_dict.values())) + file_size
    if dir_size > LIMIT_DIRECTORY_SIZE:
        return False
    return True
